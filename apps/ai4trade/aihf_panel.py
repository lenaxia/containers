#!/usr/bin/env python3
"""AIHF panel — placeholder.

Monthly CronJob target (mode `panel`). The real panel is pending
FINANCIAL_DATASETS_API_KEY + mandate wiring; this stub prints one JSON line
and exits 0 so the schedule exists and stays green until then.
"""
import json


def main():
    print(json.dumps({"ok": False,
                      "note": "ahf panel pending FINANCIAL_DATASETS_API_KEY + mandate wiring"}))


if __name__ == "__main__":
    main()
