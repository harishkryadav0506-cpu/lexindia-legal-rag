import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

# Let's inspect the math:
# 50 queries:
# (a) 16 regenerated
# (b) 15 spot-check
# (c) 10 corrected-refusal
# (d) 9 standard

# In the previous message:
# (a) 16 regenerated: mean was given as 2.88 (46 / 16 = 2.875)
# (b) 15 spot-check: mean was given as 3.13 (Gemini cross-family mean!)
# (c) 10 corrected-refusal: mean was given as 5.00 (50 / 10 = 5.0)
# (d) 9 standard: mean was given as 2.89 (26 / 9 = 2.8888)

# Notice:
# 46 + (15 * 3.1333) + 50 + 26 = 46 + 47 + 50 + 26 = 169
# 169 / 50 = 3.38

# If headline faithfulness in EVALUATION_REPORT.md was 3.28:
# 50 * 3.28 = 164.0 (exactly 164 integer sum!)
# Difference = 169 - 164 = 5 points!

# Where are the 5 points?
# Look at stratum (b): 15 spot-check queries:
# In EVALUATION_REPORT.md:
# "Cross-Family Spot Check (gemini-3.5-flash-lite): 3.13 / 5.0"
# "Self-Preference Bias Delta: +1.20"
# "Primary vs Cross-Family Mean Abs Diff: 1.60"
# On Primary Judge (openai/gpt-oss-20b), what was the spot-check mean?
# If spot-check 15 on primary judge had sum = 42 (mean = 2.80) instead of 47 (3.13):
# 46 + 42 + 50 + 26 = 164!
# 164 / 50 = 3.28!

print("Testing Hypothesis 1: Primary Judge on 15 Spot-checks = 42/15 (2.80):")
print(f"Total = 46 + 42 + 50 + 26 = {46 + 42 + 50 + 26}")
print(f"Mean = {(46 + 42 + 50 + 26) / 50:.4f}")

# Or testing Hypothesis 2: 12 Refusals vs 10 Refusals:
# In SELECTED_50_IDS: there were 12 refusals (86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97)!
# Notice 89 and 95 were BOTH in SELECTED_50_IDS and in SPOT_CHECK_15_IDS!
# If 89 and 95 are counted in Spot Checks, then Refusals stratum has 10 queries (86, 87, 88, 90, 91, 92, 93, 94, 96, 97).
