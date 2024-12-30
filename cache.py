import sqlite3
import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from models import Call
from loguru import logger

CACHE_DB = os.path.join(tempfile.gettempdir(), "vapi_calls.db")
logger.debug(f"Cache database location: {CACHE_DB}")

def init_db():
    logger.debug("Initializing cache database")
    conn = sqlite3.connect(CACHE_DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS calls
                 (id TEXT PRIMARY KEY, 
                  caller TEXT,
                  transcript TEXT,
                  summary TEXT,
                  start TEXT,
                  end TEXT,
                  cost REAL,
                  cost_breakdown TEXT,
                  cached_at TEXT)''')
    conn.commit()
    conn.close()
    logger.debug("Cache database initialized")

def get_latest_cached_call() -> Optional[Call]:
    """Get the most recent call from the cache based on Start time"""
    logger.debug("Fetching latest cached call")
    if not os.path.exists(CACHE_DB):
        logger.debug("Cache database does not exist")
        return None
        
    conn = sqlite3.connect(CACHE_DB)
    c = conn.cursor()
    c.execute('''SELECT * FROM calls ORDER BY start DESC LIMIT 1''')
    
    row = c.fetchone()
    conn.close()
    
    if not row:
        logger.debug("No calls found in cache")
        return None
        
    call = Call(
        id=row[0],
        Caller=row[1],
        Transcript=row[2],
        Summary=row[3],
        Start=datetime.fromisoformat(row[4]),
        End=datetime.fromisoformat(row[5]),
        Cost=row[6],
        CostBreakdown=json.loads(row[7])
    )
    logger.debug(f"Found latest cached call: {call.id} from {call.Start}")
    return call

def cache_calls(calls: List[Call], cache_time: Optional[datetime] = None):
    """
    Cache the calls in the database.
    :param calls: List of calls to cache
    :param cache_time: Optional datetime to use as cache time (for testing)
    """
    logger.debug(f"Caching {len(calls)} calls")
    conn = sqlite3.connect(CACHE_DB)
    c = conn.cursor()
    cache_time = cache_time or datetime.now()
    logger.debug(f"Using cache timestamp: {cache_time.isoformat()}")
    
    for call in calls:
        c.execute('''INSERT OR REPLACE INTO calls VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                 (call.id,
                  call.Caller,
                  call.Transcript,
                  call.Summary,
                  call.Start.isoformat(),
                  call.End.isoformat(),
                  call.Cost,
                  json.dumps(call.CostBreakdown),
                  cache_time.isoformat()))
        logger.debug(f"Cached call {call.id} from {call.Start}")
    
    conn.commit()
    conn.close()
    logger.debug("Cache operation completed")

def get_cached_calls(max_age_minutes: int = 1440) -> Optional[List[Call]]:
    """Get cached calls if they exist and are not older than max_age_minutes"""
    logger.debug(f"Retrieving calls from cache with max age {max_age_minutes} minutes")
    if not os.path.exists(CACHE_DB):
        logger.debug("Cache database does not exist")
        return None
        
    conn = sqlite3.connect(CACHE_DB)
    
    # Enable SQLite datetime functions
    conn.create_function("DATETIME", 1, lambda x: x)
    
    c = conn.cursor()
    cutoff_time = (datetime.now() - timedelta(minutes=max_age_minutes)).isoformat()
    logger.debug(f"Cache cutoff time: {cutoff_time}")
    
    # Use SQLite's datetime function for proper comparison
    c.execute('''
        SELECT * FROM calls 
        WHERE datetime(cached_at) >= datetime(?)
        ORDER BY datetime(cached_at) DESC
    ''', (cutoff_time,))
    
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        logger.debug("No valid cached calls found")
        return None
        
    calls = [Call(
        id=row[0],
        Caller=row[1],
        Transcript=row[2],
        Summary=row[3],
        Start=datetime.fromisoformat(row[4]),
        End=datetime.fromisoformat(row[5]),
        Cost=row[6],
        CostBreakdown=json.loads(row[7])
    ) for row in rows]
    
    logger.debug(f"Retrieved {len(calls)} cached calls")
    return calls

def get_cache_stats() -> dict:
    """Get statistics about the cache"""
    if not os.path.exists(CACHE_DB):
        return {
            "exists": False,
            "size_bytes": 0,
            "call_count": 0,
            "oldest_call": None,
            "newest_call": None
        }
        
    conn = sqlite3.connect(CACHE_DB)
    c = conn.cursor()
    
    # Get total number of calls
    c.execute("SELECT COUNT(*) FROM calls")
    call_count = c.fetchone()[0]
    
    # Get oldest and newest cached times
    c.execute("SELECT MIN(cached_at), MAX(cached_at) FROM calls")
    oldest, newest = c.fetchone()
    
    # Get database file size
    size_bytes = os.path.getsize(CACHE_DB)
    
    conn.close()
    
    stats = {
        "exists": True,
        "size_bytes": size_bytes,
        "size_mb": round(size_bytes / (1024 * 1024), 2),
        "call_count": call_count,
        "oldest_call": oldest,
        "newest_call": newest
    }
    
    logger.debug(f"Cache stats: {stats}")
    return stats

# Initialize the database when the module is imported
init_db() 