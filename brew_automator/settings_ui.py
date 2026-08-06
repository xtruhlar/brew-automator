"""Interactive terminal UI (arrow keys + space) to pick which installed
formulae/casks should be excluded from automatic upgrades.
"""

import curses

from brew_automator import ignorelist, maintenance


def _list_installed():
    """Return (formula_names, cask_names) currently installed."""
    formulae = [line for line in maintenance._run("list", "--formula").splitlines() if line]
    casks = [line for line in maintenance._run("list", "--cask").splitlines() if line]
    return formulae, casks


def _run_menu(stdscr, entries: list, preselected: set):
    """entries is a list of (kind, name) tuples. preselected is a set of indices.
    Returns the selected set of indices, or None if the user cancelled.
    """
    curses.curs_set(0)
    selected = set(preselected)
    current = 0
    top = 0

    header = [
        "brew-automator settings — exclude formulae/casks from automatic upgrades",
        "↑/↓ move   space toggle   enter save   q cancel",
        "",
    ]

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        for i, line in enumerate(header):
            stdscr.addstr(i, 0, line[: max(width - 1, 0)])

        visible_rows = max(height - len(header) - 1, 1)
        if current < top:
            top = current
        elif current >= top + visible_rows:
            top = current - visible_rows + 1

        for row, idx in enumerate(range(top, min(top + visible_rows, len(entries)))):
            kind, name = entries[idx]
            mark = "x" if idx in selected else " "
            line = f"[{mark}] ({kind}) {name}"
            y = len(header) + row
            attr = curses.A_REVERSE if idx == current else curses.A_NORMAL
            stdscr.addstr(y, 0, line[: max(width - 1, 0)], attr)

        stdscr.refresh()
        key = stdscr.getch()

        if key in (curses.KEY_UP, ord("k")):
            current = (current - 1) % len(entries)
        elif key in (curses.KEY_DOWN, ord("j")):
            current = (current + 1) % len(entries)
        elif key == ord(" "):
            if current in selected:
                selected.discard(current)
            else:
                selected.add(current)
        elif key in (curses.KEY_ENTER, 10, 13):
            return selected
        elif key in (ord("q"), 27):
            return None


def run_settings():
    """Entry point for `brew-automator settings`."""
    formulae, casks = _list_installed()
    if not formulae and not casks:
        print("No installed formulae or casks found.")
        return

    entries = [("formula", n) for n in formulae] + [("cask", n) for n in casks]
    ignored = ignorelist.load_ignored()
    preselected = {
        i
        for i, (kind, name) in enumerate(entries)
        if name in ignored["formulae" if kind == "formula" else "casks"]
    }

    result = curses.wrapper(_run_menu, entries, preselected)

    if result is None:
        print("Cancelled - no changes made.")
        return

    new_ignored = {"formulae": [], "casks": []}
    for idx in result:
        kind, name = entries[idx]
        new_ignored["formulae" if kind == "formula" else "casks"].append(name)

    ignorelist.save_ignored(new_ignored)
    print(
        f"Saved: {len(new_ignored['formulae'])} formula(e) and "
        f"{len(new_ignored['casks'])} cask(s) excluded from automatic upgrades."
    )
