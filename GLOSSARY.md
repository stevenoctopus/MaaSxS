# Glossary

Terms used in MaaSxS's code, pipeline comments and option descriptions.

**Purchase popup**: the game's popup for buying a daily-limited item with
Dawnium: a Qty field (starts at 1) with a "+", a "Daily Purchase Limit: U/L"
line (bought today / limit), and Cancel / Purchase. Used for Arena tickets,
Daily Dungeon reward attempts and Material Realms tool sets. Handled by
`agent/purchase.py`. _Not_: the Vendor Booth, where tapping a price buys
instantly with no popup.

**Daily total**: how every buy setting counts. The number set is how many
should have been bought *today*, so purchases already made today (by hand or
by an earlier run) count: the bot buys `max(0, min(wanted, limit) - bought
today)`. Running a task twice never buys twice.
