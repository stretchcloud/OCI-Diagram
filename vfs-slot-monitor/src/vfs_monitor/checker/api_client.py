"""TLScontact slot checker.

TLScontact does NOT have a public REST API. All slot checking is done
through browser automation by the SessionManager. This module is kept
for backward compatibility but delegates to SessionManager.check_slots().

For the actual scraping logic, see auth/browser_login.py:check_slots_browser().
"""
