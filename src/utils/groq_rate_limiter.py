"""
src/utils/groq_rate_limiter.py — Dynamic Pacing & Token-Aware Rate Limiter for Groq.

Dynamically inspects `x-ratelimit-remaining-tokens`, `x-ratelimit-reset-tokens`,
and token consumption from Groq response headers to pace requests proportionally.
Prevents HTTP 429 token-per-minute bursts by pacing each call based on actual
tokens consumed and sleeping until bucket reset when remaining tokens are low.
"""

import time
import re
import logging
from collections import deque
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("LexIndiaRateLimiter")


def parse_duration_seconds(duration_str: str) -> float:
    """
    Parse rate-limit duration strings from Groq headers:
    e.g. '547ms', '1.2s', '200ms', '1m26.4s', '1h13m26.4s' -> float seconds.
    """
    if not duration_str:
        return 1.0

    duration_str = str(duration_str).strip().lower()

    if duration_str.endswith("ms"):
        try:
            return max(0.05, float(duration_str[:-2]) / 1000.0)
        except ValueError:
            return 1.0

    # Match hour, minute, second components
    pattern = r'(?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?'
    match = re.match(pattern, duration_str)
    if match:
        h, m, s = match.groups()
        total_s = 0.0
        if h:
            total_s += float(h) * 3600
        if m:
            total_s += float(m) * 60
        if s:
            total_s += float(s)
        return max(0.05, total_s) if total_s > 0 else 1.0

    try:
        return max(0.05, float(duration_str.rstrip("s")))
    except ValueError:
        return 1.0


class ModelQuotaState:
    """Per-model rate limiting state."""
    def __init__(self, model_name: str, safe_token_threshold: int = 2200):
        self.model_name = model_name
        self.safe_token_threshold = safe_token_threshold
        self.limit_tokens: int = 8000
        self.remaining_tokens: int = 8000
        self.reset_duration: float = 0.6
        self.last_call_timestamp: float = 0.0
        self.earliest_next_call: float = 0.0
        self.calls_observed: int = 0
        self.rate_limits_encountered: int = 0
        self.total_tokens_consumed: int = 0
        self.token_history: deque = deque()  # (timestamp, tokens) for 60s rolling window
        self.wait_history: deque = deque()   # (timestamp, wait_s)


class GroqDynamicPacer:
    """
    Dynamic token-aware rate pacer for Groq API.
    Paces requests dynamically by:
    1. Calculating replenishment time needed for actual tokens consumed per request.
    2. Enforcing a hard wait until reset timestamp if remaining tokens drop below safe threshold.
    3. Exponential backoff on HTTP 429 respecting `retry-after` header.
    4. Tracking rolling 60-second tokens/minute (TPM) and telemetry.
    """
    def __init__(self, safe_token_threshold: int = 2200):
        self.safe_token_threshold = safe_token_threshold
        self.model_states: Dict[str, ModelQuotaState] = {}
        self.default_model = "default"

    def _get_state(self, model: Optional[str] = None) -> ModelQuotaState:
        key = model or self.default_model
        if key not in self.model_states:
            self.model_states[key] = ModelQuotaState(key, self.safe_token_threshold)
        return self.model_states[key]

    def wait_before_request(
        self,
        model: Optional[str] = None,
        estimated_tokens: int = 2200,
        safe_tpm_ceiling: Optional[int] = None
    ) -> float:
        """
        Calculates and executes necessary dynamic sleep before firing the next request.
        Adapts automatically to variable prompt/response lengths.
        Guarantees rolling 60s TPM never breaches safe ceiling:
        - 4,800 tokens for generation calls (qwen/qwen3.8-27b)
        - 6,500 tokens for judging calls (openai/gpt-oss-20b)
        Returns the number of seconds waited.
        """
        state = self._get_state(model)
        now = time.time()
        needed_wait = 0.0

        # 1. Pacing sleep from previous request token consumption
        if now < state.earliest_next_call:
            needed_wait = max(needed_wait, state.earliest_next_call - now)

        # 2. Hard guardrail: If remaining tokens reported by Groq < estimated tokens or safety floor,
        # ensure we wait until the reset timestamp
        threshold = max(state.safe_token_threshold, estimated_tokens + 200)
        if state.remaining_tokens < threshold:
            time_to_reset = (state.last_call_timestamp + state.reset_duration) - now
            if time_to_reset > 0:
                guardrail_wait = time_to_reset + 0.5  # 500ms safety buffer
                if guardrail_wait > needed_wait:
                    needed_wait = guardrail_wait
                    logger.info(
                        f"[Pacer:{state.model_name}] Remaining tokens low ({state.remaining_tokens} < {threshold}). "
                        f"Waiting {needed_wait:.2f}s for bucket reset..."
                    )

        # 3. Rolling 60s TPM Guardrail: Groq ceiling is 8,000 TPM.
        # Default: 4,800 for generation (qwen), 6,500 for judges.
        self._prune_history(state, now)
        current_tpm = sum(tok for _, tok in state.token_history)
        if safe_tpm_ceiling is None:
            is_gen = "qwen" in (state.model_name or "").lower() or (model and "qwen" in model.lower())
            ceiling = 4800 if is_gen else 6500
        else:
            ceiling = safe_tpm_ceiling

        if current_tpm + estimated_tokens > ceiling and state.token_history:
            target_excess = (current_tpm + estimated_tokens) - ceiling
            accum = 0
            t_expire = 0.0
            for ts, tok in state.token_history:
                accum += tok
                t_expire = max(t_expire, 60.0 - (now - ts) + 1.0)
                if accum >= target_excess:
                    break
            if t_expire > needed_wait:
                needed_wait = t_expire
                logger.info(
                    f"[Pacer:{state.model_name}] TPM ceiling protection: current {current_tpm} + {estimated_tokens} > {ceiling}. "
                    f"Waiting {needed_wait:.2f}s for sliding window headroom..."
                )

        if needed_wait > 0.05:
            logger.info(
                f"[Pacer:{state.model_name}] Dynamic pacing pause: {needed_wait:.2f}s "
                f"(Remaining: {state.remaining_tokens} tokens, Reset: {state.reset_duration:.2f}s, Rolling TPM: {self.get_current_tpm(model)})"
            )
            time.sleep(needed_wait)
            state.wait_history.append((time.time(), needed_wait))

        return needed_wait

    def record_response(
        self,
        headers: Dict[str, Any],
        model: Optional[str] = None,
        usage_tokens: Optional[int] = None
    ) -> None:
        """Record Groq HTTP response headers and token usage to adapt pacing."""
        state = self._get_state(model)
        now = time.time()
        state.last_call_timestamp = now
        state.calls_observed += 1

        # Case-insensitive header lookup
        h_lower = {k.lower(): v for k, v in headers.items()}

        rem_tokens_str = h_lower.get("x-ratelimit-remaining-tokens")
        reset_tokens_str = h_lower.get("x-ratelimit-reset-tokens")
        limit_tokens_str = h_lower.get("x-ratelimit-limit-tokens")

        prev_remaining = state.remaining_tokens

        if limit_tokens_str is not None:
            try:
                state.limit_tokens = int(limit_tokens_str)
            except ValueError:
                pass

        if rem_tokens_str is not None:
            try:
                state.remaining_tokens = int(rem_tokens_str)
            except ValueError:
                pass

        if reset_tokens_str is not None:
            state.reset_duration = parse_duration_seconds(reset_tokens_str)

        # Determine tokens consumed by this call
        if usage_tokens and usage_tokens > 0:
            tokens_used = usage_tokens
        elif prev_remaining > state.remaining_tokens:
            tokens_used = prev_remaining - state.remaining_tokens
        else:
            tokens_used = int(state.reset_duration * (state.limit_tokens / 60.0))

        tokens_used = max(50, min(tokens_used, 4000))
        state.total_tokens_consumed += tokens_used

        # Record in 60-second sliding window
        state.token_history.append((now, tokens_used))
        self._prune_history(state, now)

        # Dynamic replenishment pacing:
        # Groq limit is 8000 TPM. Target conservative refill rate of 100.0 tokens/sec (6,000 TPM)
        # to ensure safe operating headroom and zero 429 bursts.
        refill_rate = min(100.0, max(10.0, state.limit_tokens / 80.0))
        pacing_seconds = max(16.0, tokens_used / refill_rate)

        state.earliest_next_call = now + pacing_seconds

        # If remaining tokens fell dangerously low, push earliest call past reset
        if state.remaining_tokens < state.safe_token_threshold:
            reset_deadline = now + state.reset_duration + 0.5
            state.earliest_next_call = max(state.earliest_next_call, reset_deadline)

        logger.debug(
            f"[Pacer:{state.model_name}] Call #{state.calls_observed}: {tokens_used} tokens used. "
            f"Pacing delay: {pacing_seconds:.2f}s | Remaining: {state.remaining_tokens}/{state.limit_tokens} | Rolling TPM: {self.get_current_tpm(model)}"
        )

    def handle_rate_limit(
        self,
        retry_after_header: Optional[str] = None,
        model: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> float:
        """
        Called when HTTP 429 is encountered.
        Backs off respecting retry-after header, error body messages, and bucket reset duration.
        """
        state = self._get_state(model)
        state.rate_limits_encountered += 1
        now = time.time()

        body_wait = None
        if error_message:
            wait_match = re.search(r'try again in ([\d\w.]+)', str(error_message), re.IGNORECASE)
            if wait_match:
                body_wait = parse_duration_seconds(wait_match.group(1)) + 1.5

        header_wait = None
        if retry_after_header:
            header_wait = parse_duration_seconds(retry_after_header) + 0.5

        if body_wait and header_wait:
            sleep_time = max(body_wait, header_wait)
        elif body_wait:
            sleep_time = body_wait
        elif header_wait:
            sleep_time = header_wait
        else:
            sleep_time = max(state.reset_duration + 1.0, 8.0)

        sleep_time = min(max(sleep_time, 2.0), 15.0)
        logger.warning(
            f"[Pacer:{state.model_name}] HTTP 429 encountered! Dynamically backing off for {sleep_time:.2f}s..."
        )
        time.sleep(sleep_time)

        # After backoff, bucket is presumed reset
        state.remaining_tokens = state.limit_tokens
        state.earliest_next_call = time.time()
        return sleep_time

    def get_current_tpm(self, model: Optional[str] = None) -> int:
        """Compute rolling tokens/minute over the last 60 seconds."""
        state = self._get_state(model)
        now = time.time()
        self._prune_history(state, now)
        return sum(tokens for _, tokens in state.token_history)

    def _prune_history(self, state: ModelQuotaState, now: float) -> None:
        """Prune entries older than 60 seconds."""
        while state.token_history and now - state.token_history[0][0] > 60.0:
            state.token_history.popleft()
        while state.wait_history and now - state.wait_history[0][0] > 60.0:
            state.wait_history.popleft()

    def get_telemetry(self, model: Optional[str] = None) -> Dict[str, Any]:
        """Summary statistics for reporting."""
        state = self._get_state(model)
        now = time.time()
        self._prune_history(state, now)
        avg_wait = (
            sum(w for _, w in state.wait_history) / len(state.wait_history)
            if state.wait_history else 0.0
        )
        return {
            "model": state.model_name,
            "calls_observed": state.calls_observed,
            "rate_limits_encountered": state.rate_limits_encountered,
            "total_tokens_consumed": state.total_tokens_consumed,
            "rolling_tpm": self.get_current_tpm(model),
            "remaining_tokens": state.remaining_tokens,
            "avg_pacing_wait_s": round(avg_wait, 2),
        }

    # Compatibility attributes
    @property
    def calls_observed(self) -> int:
        return sum(s.calls_observed for s in self.model_states.values())

    @property
    def rate_limits_encountered(self) -> int:
        return sum(s.rate_limits_encountered for s in self.model_states.values())


groq_pacer = GroqDynamicPacer()

