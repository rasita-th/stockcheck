# v7.3 Mobile Memo Persistent Alert Fix

Fixes memo-alert persistence on mobile and desktop:

- Memo alerts are saved memo records, not temporary notifications.
- Opening a memo alert no longer dismisses it from the alert center.
- Memo alerts remain visible until the memo is deleted, marked Done, or ignored by the user.
- Older `memo-*` dismissed alert ids are cleaned from localStorage on load.
- Repeated browser/toast notifications are still suppressed separately, but the memo row/card remains.

This is a UI/state fix; no API changes are required.
