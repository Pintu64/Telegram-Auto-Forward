from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def keyboard(rows): return InlineKeyboardMarkup([[InlineKeyboardButton(text, callback_data=data) for text, data in row] for row in rows])
def main_menu(enabled):
    state = ("Pause forwarding", "toggle") if enabled else ("Resume forwarding", "toggle")
    return keyboard([[("Source channels", "sources"), ("Target channels", "targets")], [("Delivery mode", "mode"), state], [("Status", "status"), ("Help", "help")]])
def channel_menu(kind, has_channels):
    rows = [[(f"Add {kind}", f"add:{kind}")]]
    if has_channels: rows.append([(f"Remove {kind}", f"remove:{kind}")])
    rows.append([("Back", "home")]); return keyboard(rows)
def cancel_menu(back): return keyboard([[("Cancel", back)]])

