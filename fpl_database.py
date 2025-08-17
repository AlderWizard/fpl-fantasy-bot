#!/usr/bin/env python3
"""
Database module for FPL Bot
Handles persistent storage of league data, speech reminders, and records
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class FPLDatabase:
    def __init__(self, db_path: str = "fpl_bot.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Leagues table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS leagues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    league_id TEXT NOT NULL,
                    league_name TEXT NOT NULL,
                    added_date TEXT NOT NULL,
                    UNIQUE(chat_id, league_id)
                )
            ''')
            
            # Speech reminders table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS speech_reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    league_id TEXT NOT NULL,
                    gameweek INTEGER NOT NULL,
                    winner_name TEXT NOT NULL,
                    winner_entry_id INTEGER NOT NULL,
                    score INTEGER NOT NULL,
                    reminder_date TEXT NOT NULL,
                    completed BOOLEAN DEFAULT FALSE,
                    notified BOOLEAN DEFAULT FALSE
                )
            ''')
            
            # Records table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    league_id TEXT NOT NULL,
                    player_name TEXT NOT NULL,
                    entry_id INTEGER NOT NULL,
                    gameweek INTEGER NOT NULL,
                    score INTEGER NOT NULL,
                    record_type TEXT NOT NULL, -- 'highest' or 'lowest'
                    date_recorded TEXT NOT NULL
                )
            ''')
            
            # Gameweek tracking table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS gameweek_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    league_id TEXT NOT NULL,
                    gameweek INTEGER NOT NULL,
                    processed BOOLEAN DEFAULT FALSE,
                    processed_date TEXT,
                    UNIQUE(chat_id, league_id, gameweek)
                )
            ''')
            
            conn.commit()
    
    def add_league(self, chat_id: int, league_id: str, league_name: str) -> bool:
        """Add a league to track"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO leagues 
                    (chat_id, league_id, league_name, added_date)
                    VALUES (?, ?, ?, ?)
                ''', (chat_id, league_id, league_name, datetime.now().isoformat()))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error adding league: {e}")
            return False
    
    def get_leagues(self, chat_id: int) -> List[Dict]:
        """Get all leagues for a chat"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT league_id, league_name, added_date 
                    FROM leagues 
                    WHERE chat_id = ?
                ''', (chat_id,))
                
                leagues = []
                for row in cursor.fetchall():
                    leagues.append({
                        'league_id': row[0],
                        'league_name': row[1],
                        'added_date': row[2]
                    })
                return leagues
        except Exception as e:
            logger.error(f"Error getting leagues: {e}")
            return []
    
    def add_speech_reminder(self, chat_id: int, league_id: str, gameweek: int, 
                          winner_name: str, winner_entry_id: int, score: int) -> bool:
        """Add a speech reminder for gameweek winner"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO speech_reminders 
                    (chat_id, league_id, gameweek, winner_name, winner_entry_id, 
                     score, reminder_date, completed, notified)
                    VALUES (?, ?, ?, ?, ?, ?, ?, FALSE, FALSE)
                ''', (chat_id, league_id, gameweek, winner_name, winner_entry_id, 
                      score, datetime.now().isoformat()))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error adding speech reminder: {e}")
            return False
    
    def get_pending_speech_reminders(self, chat_id: int) -> List[Dict]:
        """Get pending speech reminders"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT sr.league_id, l.league_name, sr.gameweek, sr.winner_name, 
                           sr.score, sr.reminder_date, sr.notified
                    FROM speech_reminders sr
                    JOIN leagues l ON sr.league_id = l.league_id AND sr.chat_id = l.chat_id
                    WHERE sr.chat_id = ? AND sr.completed = FALSE
                    ORDER BY sr.gameweek DESC
                ''', (chat_id,))
                
                reminders = []
                for row in cursor.fetchall():
                    reminder_date = datetime.fromisoformat(row[5])
                    days_since = (datetime.now() - reminder_date).days
                    
                    reminders.append({
                        'league_id': row[0],
                        'league_name': row[1],
                        'gameweek': row[2],
                        'winner_name': row[3],
                        'score': row[4],
                        'days_since': days_since,
                        'notified': row[6]
                    })
                return reminders
        except Exception as e:
            logger.error(f"Error getting speech reminders: {e}")
            return []
    
    def mark_speech_completed(self, chat_id: int, league_id: str, gameweek: int) -> bool:
        """Mark a speech reminder as completed"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE speech_reminders 
                    SET completed = TRUE 
                    WHERE chat_id = ? AND league_id = ? AND gameweek = ?
                ''', (chat_id, league_id, gameweek))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error marking speech completed: {e}")
            return False
    
    def mark_speech_notified(self, chat_id: int, league_id: str, gameweek: int) -> bool:
        """Mark a speech reminder as notified"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE speech_reminders 
                    SET notified = TRUE 
                    WHERE chat_id = ? AND league_id = ? AND gameweek = ?
                ''', (chat_id, league_id, gameweek))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error marking speech notified: {e}")
            return False
    
    def update_record(self, chat_id: int, league_id: str, player_name: str, 
                     entry_id: int, gameweek: int, score: int, record_type: str) -> bool:
        """Update a record (highest or lowest score)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if this is actually a new record
                if record_type == 'highest':
                    cursor.execute('''
                        SELECT MAX(score) FROM records 
                        WHERE chat_id = ? AND league_id = ? AND record_type = 'highest'
                    ''', (chat_id, league_id))
                    current_high = cursor.fetchone()[0] or 0
                    if score <= current_high:
                        return False
                
                elif record_type == 'lowest':
                    cursor.execute('''
                        SELECT MIN(score) FROM records 
                        WHERE chat_id = ? AND league_id = ? AND record_type = 'lowest' AND score > 0
                    ''', (chat_id, league_id))
                    current_low = cursor.fetchone()[0]
                    if current_low and score >= current_low:
                        return False
                
                # Insert new record
                cursor.execute('''
                    INSERT INTO records 
                    (chat_id, league_id, player_name, entry_id, gameweek, score, record_type, date_recorded)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (chat_id, league_id, player_name, entry_id, gameweek, score, 
                      record_type, datetime.now().isoformat()))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating record: {e}")
            return False
    
    def get_records(self, chat_id: int, league_id: str = None) -> Dict:
        """Get highest and lowest scores"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                records = {'highest_score': None, 'lowest_score': None}
                
                # Get highest score
                if league_id:
                    cursor.execute('''
                        SELECT player_name, score, gameweek 
                        FROM records 
                        WHERE chat_id = ? AND league_id = ? AND record_type = 'highest'
                        ORDER BY score DESC LIMIT 1
                    ''', (chat_id, league_id))
                else:
                    cursor.execute('''
                        SELECT r.player_name, r.score, r.gameweek, l.league_name
                        FROM records r
                        JOIN leagues l ON r.league_id = l.league_id AND r.chat_id = l.chat_id
                        WHERE r.chat_id = ? AND r.record_type = 'highest'
                        ORDER BY r.score DESC LIMIT 1
                    ''', (chat_id,))
                
                row = cursor.fetchone()
                if row:
                    records['highest_score'] = {
                        'player': row[0],
                        'score': row[1],
                        'gameweek': row[2],
                        'league': row[3] if not league_id else None
                    }
                
                # Get lowest score
                if league_id:
                    cursor.execute('''
                        SELECT player_name, score, gameweek 
                        FROM records 
                        WHERE chat_id = ? AND league_id = ? AND record_type = 'lowest' AND score > 0
                        ORDER BY score ASC LIMIT 1
                    ''', (chat_id, league_id))
                else:
                    cursor.execute('''
                        SELECT r.player_name, r.score, r.gameweek, l.league_name
                        FROM records r
                        JOIN leagues l ON r.league_id = l.league_id AND r.chat_id = l.chat_id
                        WHERE r.chat_id = ? AND r.record_type = 'lowest' AND r.score > 0
                        ORDER BY r.score ASC LIMIT 1
                    ''', (chat_id,))
                
                row = cursor.fetchone()
                if row:
                    records['lowest_score'] = {
                        'player': row[0],
                        'score': row[1],
                        'gameweek': row[2],
                        'league': row[3] if not league_id else None
                    }
                
                return records
        except Exception as e:
            logger.error(f"Error getting records: {e}")
            return {'highest_score': None, 'lowest_score': None}
    
    def is_gameweek_processed(self, chat_id: int, league_id: str, gameweek: int) -> bool:
        """Check if a gameweek has been processed for speech reminders"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT processed FROM gameweek_tracking 
                    WHERE chat_id = ? AND league_id = ? AND gameweek = ?
                ''', (chat_id, league_id, gameweek))
                
                row = cursor.fetchone()
                return row and row[0]
        except Exception as e:
            logger.error(f"Error checking gameweek processed: {e}")
            return False
    
    def mark_gameweek_processed(self, chat_id: int, league_id: str, gameweek: int) -> bool:
        """Mark a gameweek as processed"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO gameweek_tracking 
                    (chat_id, league_id, gameweek, processed, processed_date)
                    VALUES (?, ?, ?, TRUE, ?)
                ''', (chat_id, league_id, gameweek, datetime.now().isoformat()))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error marking gameweek processed: {e}")
            return False
