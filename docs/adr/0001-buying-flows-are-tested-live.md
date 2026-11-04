# Buying flows are tested live, not offline

The offline tests (`tests/`, through `tools/still.py`) check what the agent
*reads* off one saved screen: discounts, badges, track rewards, popup
numbers. They don't check *flows*, such as how many to buy, when a refresh
happened, or stopping for "not enough Dawnium". Those need the screen to
change after each tap.

We decided not to build an offline adapter that steps through captured
screens on each tap. It would have to simulate the game screen by screen
(which tap leads where, popups, counts going up), and keeping it in step
with the game would cost more than it catches. Flows are checked live with
`tools/run.py`, using overrides so nothing is spent (for example, pointing
`Common_Purchase_Purchase` at Cancel and making runs do nothing).
