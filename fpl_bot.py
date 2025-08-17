#!/usr/bin/env python3
"""
Premier League Fantasy Football Telegram Bot
Features:
- Show league stats (scores, ranks)
- Track lowest/highest scores overall
- Remind gameweek winners to write speeches
"""

import os
import json
import logging
import asyncio
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

from fpl_database import FPLDatabase

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# FPL API Base URL
FPL_API_BASE = "https://fantasy.premierleague.com/api"

class FPLBot:
    def __init__(self, token: str):
        self.token = token
        self.application = Application.builder().token(token).build()
        self.db = FPLDatabase()
        
        # Add handlers
        self.setup_handlers()
        
        # Start background tasks
        self.application.job_queue.run_repeating(
            self.check_gameweek_winners, 
            interval=3600,  # Check every hour
            first=10
        )
        self.application.job_queue.run_repeating(
            self.send_speech_reminders,
            interval=86400,  # Check daily
            first=60
        )
    
    def setup_handlers(self):
        """Set up command and message handlers"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("addleague", self.add_league_command))
        self.application.add_handler(CommandHandler("leagues", self.list_leagues_command))
        self.application.add_handler(CommandHandler("stats", self.league_stats_command))
        self.application.add_handler(CommandHandler("records", self.records_command))
        self.application.add_handler(CommandHandler("speech", self.speech_reminder_command))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler"""
        welcome_text = (
            "🏆 **Premier League Fantasy Football Bot** 🏆\n\n"
            "Welcome! I can help you track your FPL league stats.\n\n"
            "**Commands:**\n"
            "• `/addleague <league_id>` - Add a league to track\n"
            "• `/leagues` - View tracked leagues\n"
            "• `/stats <league_id>` - Show league standings\n"
            "• `/records` - Show highest/lowest scores\n"
            "• `/speech` - Check speech reminders\n"
            "• `/help` - Show this help message\n\n"
            "To get started, add a league with `/addleague <your_league_id>`"
        )
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command handler"""
        await self.start_command(update, context)
    
    async def add_league_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add a league to track"""
        if not context.args:
            await update.message.reply_text(
                "Please provide a league ID. Example: `/addleague 123456`",
                parse_mode='Markdown'
            )
            return
        
        league_id = context.args[0]
        chat_id = update.effective_chat.id
        
        # Validate league ID
        league_data = await self.fetch_league_data(league_id)
        if not league_data:
            await update.message.reply_text(
                f"❌ Could not find league with ID: {league_id}\n"
                "Please check the league ID and try again."
            )
            return
        
        # Store league data in database
        league_name = league_data.get('league', {}).get('name', 'Unknown League')
        success = self.db.add_league(chat_id, league_id, league_name)
        
        if not success:
            await update.message.reply_text(
                "❌ Failed to add league to database. Please try again."
            )
            return
        
        await update.message.reply_text(
            f"✅ Successfully added league: **{league_data['league']['name']}**\n"
            f"League ID: `{league_id}`\n\n"
            f"Use `/stats {league_id}` to view standings!",
            parse_mode='Markdown'
        )
    
    async def list_leagues_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all tracked leagues"""
        chat_id = update.effective_chat.id
        
        leagues = self.db.get_leagues(chat_id)
        
        if not leagues:
            await update.message.reply_text(
                "No leagues tracked yet. Add one with `/addleague <league_id>`",
                parse_mode='Markdown'
            )
            return
        
        leagues_text = "📋 **Tracked Leagues:**\n\n"
        for league in leagues:
            leagues_text += f"• **{league['league_name']}** (ID: `{league['league_id']}`)\n"
        
        leagues_text += f"\nUse `/stats <league_id>` to view standings!"
        
        await update.message.reply_text(leagues_text, parse_mode='Markdown')
    
    async def league_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show league standings and stats"""
        chat_id = update.effective_chat.id
        
        # If league ID provided, use it directly
        if context.args:
            league_id = context.args[0]
            await self.show_league_stats(update, league_id)
            return
        
        # No league ID provided - check tracked leagues
        leagues = self.db.get_leagues(chat_id)
        
        if not leagues:
            await update.message.reply_text(
                "No leagues tracked yet. Add one with `/addleague <league_id>`",
                parse_mode='Markdown'
            )
            return
        
        # If only one league tracked, show it automatically
        if len(leagues) == 1:
            league_id = leagues[0]['league_id']
            await self.show_league_stats(update, league_id)
            return
        
        # Multiple leagues - show selection menu
        keyboard = []
        for league in leagues:
            keyboard.append([
                InlineKeyboardButton(
                    f"📊 {league['league_name']}", 
                    callback_data=f"stats_{league['league_id']}"
                )
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📋 **Select a league to view stats:**",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def show_league_stats(self, update: Update, league_id: str):
        """Display stats for a specific league"""
        await update.message.reply_text("🔄 Fetching league data...")
        
        league_data = await self.fetch_league_data(league_id)
        if not league_data:
            await update.message.reply_text(
                f"❌ Could not fetch data for league ID: {league_id}"
            )
            return
        
        # Format league standings
        standings_text = await self.format_league_standings(league_data)
        
        # Create inline keyboard for additional options
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{league_id}")],
            [InlineKeyboardButton("📊 Records", callback_data=f"records_{league_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            standings_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def records_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show highest and lowest scores across all tracked leagues"""
        chat_id = update.effective_chat.id
        
        leagues = self.db.get_leagues(chat_id)
        
        if not leagues:
            await update.message.reply_text(
                "No leagues tracked yet. Add one with `/addleague <league_id>`",
                parse_mode='Markdown'
            )
            return
        
        await update.message.reply_text("🔄 Analyzing records across all leagues...")
        
        all_records = self.db.get_records(chat_id)
        records_text = await self.format_records(all_records)
        
        await update.message.reply_text(records_text, parse_mode='Markdown')
    
    async def speech_reminder_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check and manage speech reminders"""
        chat_id = update.effective_chat.id
        
        leagues = self.db.get_leagues(chat_id)
        
        if not leagues:
            await update.message.reply_text(
                "No leagues tracked yet. Add one with `/addleague <league_id>`",
                parse_mode='Markdown'
            )
            return
        
        # Check for pending speech reminders
        pending_speeches = self.db.get_pending_speech_reminders(chat_id)
        
        if not pending_speeches:
            await update.message.reply_text(
                "✅ No pending speech reminders at the moment!"
            )
            return
        
        speech_text = "🎤 **Speech Reminders:**\n\n"
        for reminder in pending_speeches:
            status_emoji = "⚠️" if reminder['days_since'] >= 3 else "🔔"
            speech_text += (
                f"{status_emoji} **{reminder['league_name']}** (GW{reminder['gameweek']})\n"
                f"👑 Winner: {reminder['winner_name']}\n"
                f"📊 Score: {reminder['score']} points\n"
                f"⏰ {reminder['days_since']} days ago\n\n"
            )
        
        speech_text += "Speeches are automatically cleared when the next gameweek finishes."
        await update.message.reply_text(speech_text, parse_mode='Markdown')
    
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data.startswith("refresh_"):
            league_id = data.split("_")[1]
            await query.edit_message_text("🔄 Refreshing league data...")
            
            league_data = await self.fetch_league_data(league_id)
            if league_data:
                standings_text = await self.format_league_standings(league_data)
                
                keyboard = [
                    [InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{league_id}")],
                    [InlineKeyboardButton("📊 Records", callback_data=f"records_{league_id}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    standings_text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            else:
                await query.edit_message_text("❌ Failed to refresh league data")
        
        elif data.startswith("records_"):
            league_id = data.split("_")[1]
            await query.edit_message_text("🔄 Fetching records...")
            
            # Get records for specific league
            league_records = self.db.get_records(query.message.chat_id, league_id)
            records_text = await self.format_single_league_records(league_records, league_id)
            
            await query.edit_message_text(records_text, parse_mode='Markdown')
        
        elif data.startswith("stats_"):
            league_id = data.split("_")[1]
            await query.edit_message_text("🔄 Fetching league data...")
            
            league_data = await self.fetch_league_data(league_id)
            if league_data:
                standings_text = await self.format_league_standings(league_data)
                
                keyboard = [
                    [InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{league_id}")],
                    [InlineKeyboardButton("📊 Records", callback_data=f"records_{league_id}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    standings_text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            else:
                await query.edit_message_text("❌ Failed to fetch league data")
    
    async def fetch_league_data(self, league_id: str) -> Optional[Dict]:
        """Fetch league data from FPL API"""
        try:
            url = f"{FPL_API_BASE}/leagues-classic/{league_id}/standings/"
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to fetch league {league_id}: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching league data: {e}")
            return None
    
    async def fetch_manager_history(self, manager_id: str) -> Optional[Dict]:
        """Fetch manager's gameweek history"""
        try:
            url = f"{FPL_API_BASE}/entry/{manager_id}/history/"
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return response.json()
            else:
                return None
        except Exception as e:
            logger.error(f"Error fetching manager history: {e}")
            return None
    
    async def format_league_standings(self, league_data: Dict) -> str:
        """Format league standings into readable text"""
        league_info = league_data.get('league', {})
        standings = league_data.get('standings', {}).get('results', [])
        
        if not standings:
            return "❌ No standings data available"
        
        text = f"🏆 **{league_info.get('name', 'League')}**\n"
        text += f"📊 **Current Standings:**\n\n"
        
        total_players = len(standings)
        display_count = min(10, total_players)
        
        for i, entry in enumerate(standings[:display_count], 1):
            # Special emojis for positions
            if i == 1:
                rank_emoji = "🥇"  # Gold medal for 1st
            elif i == 2:
                rank_emoji = "🥈"  # Silver medal for 2nd  
            elif i == 3:
                rank_emoji = "🥉"  # Bronze medal for 3rd
            elif i == total_players and total_players > 3:
                rank_emoji = f"💩 {i}."  # Poo emoji for last place
            else:
                rank_emoji = f"{i}."
            
            text += (
                f"{rank_emoji} **{entry['player_name']}** ({entry['entry_name']})\n"
                f"   📈 {entry['total']} pts | GW: {entry['event_total']} pts\n\n"
            )
        
        # Show last place if we have more than 10 players and aren't already showing them
        if total_players > 10:
            text += f"... and {total_players - 10} more players\n\n"
            
            # Show last place with poo emoji
            last_player = standings[-1]
            text += (
                f"💩 {total_players}. **{last_player['player_name']}** ({last_player['entry_name']})\n"
                f"   📉 {last_player['total']} pts | GW: {last_player['event_total']} pts\n"
                f"   *({total_players}th place)*\n\n"
            )
        
        text += f"🔢 Total Players: {total_players}\n\n"
        
        # Add motivational/pressure messages
        if total_players >= 2:
            first_place = standings[0]
            last_place = standings[-1]
            
            if total_players >= 3:
                second_place = standings[1]
                second_last = standings[-2]
                
                # Pressure message for first place
                points_gap_to_second = first_place['total'] - second_place['total']
                if points_gap_to_second <= 50:  # Close race
                    text += f"🔥 **{first_place['player_name']}**, watch out! **{second_place['player_name']}** is only {points_gap_to_second} points behind you! 👀\n\n"
                
                # Motivation for last place
                points_needed = second_last['total'] - last_place['total']
                if points_needed <= 100:  # Catchable gap
                    text += f"💪 **{last_place['player_name']}**, you can do this! You only need {points_needed} points to catch **{second_last['player_name']}**! 🚀"
                else:
                    text += f"🎯 **{last_place['player_name']}**, keep fighting! Every point counts - you're still in this! 💪"
            else:
                # Only 2 players - head to head
                points_gap = first_place['total'] - last_place['total']
                text += f"⚔️ Head-to-head battle! **{first_place['player_name']}** leads by {points_gap} points, but **{last_place['player_name']}** is hunting! 🏹"
        
        return text
    
    async def process_league_for_records(self, chat_id: int, league_id: str):
        """Process a league to update records and check for gameweek winners"""
        league_data = await self.fetch_league_data(league_id)
        if not league_data:
            return
        
        standings = league_data.get('standings', {}).get('results', [])
        
        for entry in standings:
            manager_id = entry['entry']
            history = await self.fetch_manager_history(str(manager_id))
            
            if history and 'current' in history:
                for gw in history['current']:
                    score = gw['points']
                    gameweek = gw['event']
                    
                    if score > 0:
                        # Update records
                        self.db.update_record(
                            chat_id, league_id, entry['player_name'], 
                            manager_id, gameweek, score, 'highest'
                        )
                        self.db.update_record(
                            chat_id, league_id, entry['player_name'], 
                            manager_id, gameweek, score, 'lowest'
                        )
        
        # Check for gameweek winners (most recent completed gameweek)
        await self.check_gameweek_winner(chat_id, league_id, league_data)
    
    async def check_gameweek_winner(self, chat_id: int, league_id: str, league_data: Dict):
        """Check for gameweek winner and create speech reminder"""
        # Get current gameweek from API
        try:
            url = f"{FPL_API_BASE}/bootstrap-static/"
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                bootstrap_data = response.json()
                events = bootstrap_data.get('events', [])
                
                # Find most recent finished gameweek
                current_gw = None
                for event in events:
                    if event['finished'] and not event['data_checked']:
                        current_gw = event['id']
                        break
                
                if not current_gw:
                    return
                
                # Check if we've already processed this gameweek
                if self.db.is_gameweek_processed(chat_id, league_id, current_gw):
                    return
                
                # Find gameweek winner
                await self.find_gameweek_winner(chat_id, league_id, current_gw)
                
                # Mark gameweek as processed
                self.db.mark_gameweek_processed(chat_id, league_id, current_gw)
        
        except Exception as e:
            logger.error(f"Error checking gameweek winner: {e}")
    
    async def find_gameweek_winner(self, chat_id: int, league_id: str, gameweek: int):
        """Find the winner of a specific gameweek"""
        league_data = await self.fetch_league_data(league_id)
        if not league_data:
            return
        
        standings = league_data.get('standings', {}).get('results', [])
        highest_score = 0
        winner = None
        
        for entry in standings:
            manager_id = entry['entry']
            history = await self.fetch_manager_history(str(manager_id))
            
            if history and 'current' in history:
                for gw in history['current']:
                    if gw['event'] == gameweek and gw['points'] > highest_score:
                        highest_score = gw['points']
                        winner = {
                            'name': entry['player_name'],
                            'entry_id': manager_id,
                            'score': gw['points']
                        }
        
        if winner:
            # Add speech reminder
            self.db.add_speech_reminder(
                chat_id, league_id, gameweek, 
                winner['name'], winner['entry_id'], winner['score']
            )
    
    async def format_records(self, records: Dict) -> str:
        """Format records into readable text"""
        text = "📊 **All-Time Records:**\n\n"
        
        if records['highest_score']:
            high = records['highest_score']
            league_text = f" ({high['league']})" if high.get('league') else ""
            text += (
                f"🔥 **Highest Score:**\n"
                f"👑 {high['player']} - **{high['score']} points**\n"
                f"🏆 GW{high['gameweek']}{league_text}\n\n"
            )
        
        if records['lowest_score']:
            low = records['lowest_score']
            league_text = f" ({low['league']})" if low.get('league') else ""
            text += (
                f"💀 **Lowest Score:**\n"
                f"😬 {low['player']} - **{low['score']} points**\n"
                f"🏆 GW{low['gameweek']}{league_text}\n\n"
            )
        
        if not records['highest_score'] and not records['lowest_score']:
            text += "No records found yet. Add some leagues and check back!"
        
        return text
    
    async def format_single_league_records(self, records: Dict, league_id: str) -> str:
        """Format records for a single league"""
        text = f"📊 **League Records (ID: {league_id}):**\n\n"
        
        if records['highest_score']:
            high = records['highest_score']
            text += (
                f"🔥 **Highest Score:**\n"
                f"👑 {high['player']} - **{high['score']} points** (GW{high['gameweek']})\n\n"
            )
        
        if records['lowest_score']:
            low = records['lowest_score']
            text += (
                f"💀 **Lowest Score:**\n"
                f"😬 {low['player']} - **{low['score']} points** (GW{low['gameweek']})\n\n"
            )
        
        if not records['highest_score'] and not records['lowest_score']:
            text += "No records found for this league yet."
        
        return text
    
    async def check_gameweek_winners(self, context: ContextTypes.DEFAULT_TYPE):
        """Background task to check for new gameweek winners"""
        try:
            # Get all tracked leagues from database
            # This is a simplified version - in production you'd iterate through all chats
            logger.info("Checking for gameweek winners...")
            
            # For now, we'll process this when users interact with the bot
            # A full implementation would require storing chat IDs and processing all leagues
            
        except Exception as e:
            logger.error(f"Error in gameweek winner check: {e}")
    
    async def send_speech_reminders(self, context: ContextTypes.DEFAULT_TYPE):
        """Background task to send speech reminders"""
        try:
            logger.info("Checking for speech reminders to send...")
            
            # This would iterate through all chats and send reminders
            # For now, users can check manually with /speech command
            
        except Exception as e:
            logger.error(f"Error sending speech reminders: {e}")
    
    def run(self):
        """Start the bot"""
        logger.info("Starting FPL Bot...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

def main():
    """Main function"""
    # Get bot token from environment variable
    token = os.getenv('FPL_TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("FPL_TELEGRAM_BOT_TOKEN environment variable not set")
        return
    
    # Create and run bot
    bot = FPLBot(token)
    bot.run()

if __name__ == '__main__':
    main()
