from __future__ import annotations
import html, logging
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
from .database import Database
from .service import ForwardingService
from .ui import cancel_menu, channel_menu, keyboard, main_menu
LOGGER = logging.getLogger(__name__)

class ControlBot:
    def __init__(self, token, owner_user_id, database: Database, service: ForwardingService):
        self.owner_user_id, self.database, self.service = owner_user_id, database, service
        self.application = Application.builder().token(token).build()
        self.application.add_handler(CommandHandler("start", self.start)); self.application.add_handler(CommandHandler("cancel", self.start))
        self.application.add_handler(CallbackQueryHandler(self.on_button)); self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.on_text)); self.application.add_error_handler(self.on_error)
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await self._authorized(update): context.user_data.clear(); await self._show_home(update)
    async def on_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._authorized(update) or update.callback_query is None: return
        query, action = update.callback_query, update.callback_query.data or "home"; await query.answer(); context.user_data.clear()
        if action == "home": await self._show_home(update)
        elif action in {"sources", "targets"}: await self._show_channels(update, action[:-1])
        elif action.startswith("add:"):
            kind = action.split(":", 1)[1]; context.user_data["awaiting"] = f"add:{kind}"
            await query.edit_message_text(f"Send the {kind} channel username, t.me link, or numeric channel ID.", reply_markup=cancel_menu(f"{kind}s"))
        elif action.startswith("remove:"): await self._show_remove(update, action.split(":", 1)[1])
        elif action.startswith("delete:"):
            _, kind, raw_id = action.split(":", 2); self.database.remove_channel(kind, int(raw_id)); await self._show_channels(update, kind, "Channel removed.")
        elif action == "toggle":
            enabled = self.database.get_setting("enabled") != "1"; self.database.set_setting("enabled", "1" if enabled else "0"); await self._show_home(update, "Forwarding resumed." if enabled else "Forwarding paused.")
        elif action == "mode":
            current = self.database.get_setting("mode")
            await query.edit_message_text(f"<b>Delivery mode</b>\n\nCurrent: <b>{current.title()}</b>", parse_mode=ParseMode.HTML, reply_markup=keyboard([[("Forward with attribution", "setmode:forward")], [("Copy without attribution", "setmode:copy")], [("Back", "home")]]))
        elif action.startswith("setmode:"):
            mode = action.split(":", 1)[1]; self.database.set_setting("mode", mode); await self._show_home(update, f"Delivery mode set to {mode}.")
        elif action == "status": await self._show_status(update)
        elif action == "help": await query.edit_message_text("<b>Help</b>\n\nThe signed-in user account must view every source and post in every target. Only new posts are processed. Protected content cannot be relayed.\n\nUse /cancel to return home.", parse_mode=ParseMode.HTML, reply_markup=keyboard([[("Back", "home")]]))
    async def on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._authorized(update) or update.effective_message is None: return
        awaiting = context.user_data.get("awaiting", "")
        if not awaiting.startswith("add:"): await self._show_home(update, "Choose an action from the menu."); return
        kind = awaiting.split(":", 1)[1]
        try: channel = await self.service.resolve_channel(update.effective_message.text or ""); self.database.add_channel(kind, channel)
        except Exception as error:
            LOGGER.info("Could not resolve channel: %s", error); await update.effective_message.reply_text("I could not access that channel. Check the username/ID and make sure your signed-in account can open it.", reply_markup=cancel_menu(f"{kind}s")); return
        context.user_data.clear(); await update.effective_message.reply_text(f"Added {html.escape(channel.label)} as a {kind}.", reply_markup=channel_menu(kind, True))
    async def _show_home(self, update, notice=None):
        enabled = self.database.get_setting("enabled") == "1"; state = "Running" if enabled else "Paused"; text = "<b>Auto Forwarder</b>\n" + (f"\n{html.escape(notice)}\n" if notice else "\n") + f"Status: <b>{state}</b>"; await self._render(update, text, main_menu(enabled))
    async def _show_channels(self, update, kind, notice=None):
        channels = self.database.channels(kind); lines = [f"<b>{kind.title()} channels</b>"]
        if notice: lines.extend(("", html.escape(notice)))
        lines.extend(("", *(f"{index}. {html.escape(channel.label)}" for index, channel in enumerate(channels, 1))))
        if not channels: lines.append("No channels added yet.")
        await self._render(update, "\n".join(lines), channel_menu(kind, bool(channels)))
    async def _show_remove(self, update, kind):
        rows = [[(channel.title[:40], f"delete:{kind}:{channel.chat_id}")] for channel in self.database.channels(kind)]; rows.append([("Back", f"{kind}s")]); await self._render(update, f"Select a {kind} to remove:", keyboard(rows))
    async def _show_status(self, update):
        enabled = self.database.get_setting("enabled") == "1"; mode = self.database.get_setting("mode").title(); text = f"<b>Service status</b>\n\nForwarding: <b>{'Running' if enabled else 'Paused'}</b>\nMode: <b>{mode}</b>\nSources: <b>{len(self.database.channels('source'))}</b>\nTargets: <b>{len(self.database.channels('target'))}</b>"; await self._render(update, text, keyboard([[("Back", "home")]]))
    async def _render(self, update, text, markup):
        if update.callback_query: await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
        elif update.effective_message: await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    async def _authorized(self, update):
        user = update.effective_user
        if user and user.id == self.owner_user_id: return True
        if update.effective_message: await update.effective_message.reply_text("This is a private control bot.")
        elif update.callback_query: await update.callback_query.answer("Not authorized.", show_alert=True)
        return False
    async def on_error(self, update, context): LOGGER.exception("Control bot update failed", exc_info=context.error)

