"""
Caching utilities for the Win Probability Chart API.

Design Pattern: Decorator Pattern for caching
Algorithm: Dictionary-based cache with timestamp expiration + file persistence
Big O: O(1) for get/set operations, O(n) for save/load where n = cache size

Environment Variables:
    CACHE: Set to "false" to disable all caching (default: "true")
           Usage: CACHE=false uvicorn api.main:app --reload --port 8000
"""

import time
import pickle
import os
import threading
from pathlib import Path
from typing import Any, Callable, Optional
from functools import wraps

from .logging_config import get_logger, DEBUG_MODE

logger = get_logger(__name__)

# Global cache enable/disable flag (can be disabled via CACHE=false environment variable)
# Default is True (caching enabled)
CACHE_ENABLED = os.environ.get("CACHE", "true").lower() not in ("false", "0", "no", "off")

if not CACHE_ENABLED:
    logger.warning("[CACHE] ⚠️  Caching is DISABLED (CACHE environment variable set to false)")
else:
    logger.info("[CACHE] Caching is enabled (default)")

# Cache directory (persists across server reloads)
CACHE_DIR = Path(__file__).parent.parent / ".cache"
CACHE_DIR.mkdir(exist_ok=True)


class SimpleCache:
    """
    Simple in-memory cache with TTL (time-to-live) and file persistence.
    
    Persists cache to disk so it survives server reloads during development.
    
    Design Pattern: Decorator Pattern for caching + Persistence Layer
    Algorithm: Dictionary-based cache with timestamp expiration + pickle serialization
    Big O: O(1) for get/set operations, O(n) for save/load where n = cache size
    """
    def __init__(self, ttl_seconds: int = 300, cache_file: Optional[str] = None):  # Default 5 minutes
        # Cache format: {key: (value, timestamp, ttl, data_version)}
        # data_version is optional - if provided, cache is invalidated when it changes
        self.cache: dict[str, tuple[Any, float, int, Optional[Any]]] = {}
        self.default_ttl = ttl_seconds
        self.cache_file = cache_file
        if cache_file:
            self._load_from_disk()
    
    def _get_cache_path(self) -> Optional[Path]:
        """Get the full path to the cache file."""
        if not self.cache_file:
            return None
        return CACHE_DIR / self.cache_file
    
    def _load_from_disk(self) -> None:
        """Load cache from disk if it exists."""
        cache_path = self._get_cache_path()
        if not cache_path:
            return
        
        if not cache_path.exists():
            if self.cache_file and "aggregate_stats" in self.cache_file:
                logger.info(f"Cache file does not exist yet: {cache_path.name}")
            else:
                logger.debug(f"Cache file does not exist yet: {cache_path.name}")
            return
        
        try:
            # Use builtins.open to avoid issues during shutdown when 'open' might not be in scope
            import builtins
            with builtins.open(cache_path, 'rb') as f:
                loaded_cache = pickle.load(f)
                # Filter out expired entries on load
                # Handle both old format (value, timestamp, ttl) and new format (value, timestamp, ttl, data_version)
                current_time = time.time()
                valid_entries = {}
                for k, v in loaded_cache.items():
                    if len(v) == 3:
                        # Old format: (value, timestamp, ttl) - migrate to new format
                        value, timestamp, ttl = v
                        if current_time - timestamp < ttl:
                            valid_entries[k] = (value, timestamp, ttl, None)
                    elif len(v) == 4:
                        # New format: (value, timestamp, ttl, data_version)
                        if current_time - v[1] < v[2]:  # age < ttl
                            valid_entries[k] = v
                expired_count = len(loaded_cache) - len(valid_entries)
                self.cache = valid_entries
                
                if self.cache_file and "aggregate_stats" in self.cache_file:
                    logger.info(f"Loaded {len(self.cache)} valid cache entries from {cache_path.name} (expired: {expired_count})")
                elif DEBUG_MODE:
                    logger.debug(f"Loaded {len(self.cache)} cache entries from {cache_path.name} (expired: {expired_count})")
        except Exception as e:
            logger.warning(f"Failed to load cache from {cache_path}: {e}")
            self.cache = {}
    
    def _save_to_disk(self) -> None:
        """Save cache to disk."""
        cache_path = self._get_cache_path()
        if not cache_path:
            return
        
        # Check if Python is shutting down (sys.meta_path becomes None during shutdown)
        try:
            import sys
            if sys.meta_path is None:
                # Python is shutting down, skip saving silently
                return
        except (AttributeError, RuntimeError):
            # sys might not be available or in inconsistent state during shutdown
            return
        
        try:
            # Only save non-expired entries
            current_time = time.time()
            valid_cache = {
                k: v for k, v in self.cache.items()
                if current_time - v[1] < v[2]  # age < ttl
            }
            
            # Use builtins.open to avoid issues during shutdown when 'open' might not be in scope
            import builtins
            with builtins.open(cache_path, 'wb') as f:
                pickle.dump(valid_cache, f)
            
            if DEBUG_MODE:
                logger.debug(f"Saved {len(valid_cache)} cache entries to {cache_path.name}")
        except (Exception, RuntimeError, AttributeError) as e:
            # Silently ignore errors during Python shutdown
            # Check if Python is shutting down by checking sys.meta_path
            try:
                import sys
                if sys.meta_path is None:
                    # Python is shutting down, don't log warning
                    return
            except (AttributeError, RuntimeError):
                # sys might not be available, assume shutdown
                return
            # Only log warning if not shutting down
            logger.warning(f"Failed to save cache to {cache_path}: {e}")
    
    def get(self, key: str, data_version: Optional[Any] = None) -> Optional[Any]:
        """
        Get value from cache if not expired and data version matches.
        
        Args:
            key: Cache key
            data_version: Optional data version to check. If provided and different from cached version, cache is invalidated.
        
        Returns:
            Cached value if valid, None otherwise
        """
        # Respect global CACHE_ENABLED flag
        if not CACHE_ENABLED:
            return None
        
        if key in self.cache:
            entry = self.cache[key]
            if len(entry) == 3:
                # Old format: (value, timestamp, ttl) - migrate
                value, timestamp, ttl = entry
                cached_data_version = None
            else:
                # New format: (value, timestamp, ttl, data_version)
                value, timestamp, ttl, cached_data_version = entry
            
            # Check if expired
            if time.time() - timestamp >= ttl:
                return None
            
            # Check data version if provided
            if data_version is not None:
                if cached_data_version != data_version:
                    logger.info(f"[CACHE] Data version mismatch for key {key[:60]}... (cached: {cached_data_version}, current: {data_version})")
                    # Remove invalidated entry
                    del self.cache[key]
                    return None
            age = time.time() - timestamp
            if age < ttl:
                if DEBUG_MODE:
                    logger.debug(f"Cache HIT: {key[:50]}... (age: {age:.1f}s, ttl: {ttl}s)")
                return value
            else:
                # Expired, remove it
                if DEBUG_MODE:
                    logger.debug(f"Cache EXPIRED: {key[:50]}... (age: {age:.1f}s, ttl: {ttl}s)")
                del self.cache[key]
        else:
            if DEBUG_MODE:
                logger.debug(f"Cache MISS: {key[:50]}...")
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None, data_version: Optional[Any] = None) -> None:
        """Store value in cache with current timestamp and optional data version."""
        # Respect global CACHE_ENABLED flag
        if not CACHE_ENABLED:
            return
        
        actual_ttl = ttl if ttl is not None else self.default_ttl
        self.cache[key] = (value, time.time(), actual_ttl, data_version)
        if DEBUG_MODE:
            logger.debug(f"Cache SET: {key[:50]}... (ttl: {actual_ttl}s)")
        # Save to disk periodically (every 10th set to avoid too much I/O)
        if len(self.cache) % 10 == 0:
            self._save_to_disk()
    
    def save(self) -> None:
        """Force save cache to disk immediately."""
        self._save_to_disk()
    
    def clear(self) -> None:
        """Clear all cached entries."""
        self.cache.clear()
        self._save_to_disk()  # Persist the clear
    
    def invalidate(self, key_pattern: str) -> None:
        """Invalidate cache entries matching a pattern (e.g., 'game_401810151_*')."""
        keys_to_remove = [k for k in self.cache.keys() if key_pattern in k]
        for k in keys_to_remove:
            del self.cache[k]
        if keys_to_remove:
            self._save_to_disk()  # Persist the invalidation
    
    def __del__(self):
        """Save cache to disk when cache instance is destroyed."""
        try:
            self._save_to_disk()
        except Exception:
            pass  # Ignore errors during cleanup


# Track background refresh tasks to avoid duplicate calculations
_background_refresh_locks: dict[str, threading.Lock] = {}
_background_refresh_locks_lock = threading.Lock()
_background_refresh_status: dict[str, bool] = {}  # Track if refresh is in progress
_background_refresh_initiated: dict[str, bool] = {}  # Track if refresh has been initiated this app session


def get_refresh_status(func_name: str) -> bool:
    """Check if a background refresh is in progress for a function."""
    status = _background_refresh_status.get(func_name, False)
    if DEBUG_MODE:
        logger.debug(f"[CACHE] get_refresh_status({func_name}): {status}")
    return status


def cached(ttl_seconds: int = 300, dynamic_ttl: Optional[Callable[[Any], int]] = None, background_refresh: bool = False, data_version_check: Optional[Callable[[], Any]] = None):
    """
    Decorator to cache function results with file persistence.
    
    Cache persists across server reloads (stored in .cache/ directory).
    
    Args:
        ttl_seconds: Time-to-live for cached results (default: 5 minutes)
        dynamic_ttl: Optional function that takes the result and returns a TTL in seconds.
                    Useful for caching completed games longer than in-progress games.
        background_refresh: If True, return stale cache immediately and refresh in background.
                          Useful for expensive calculations where stale data is acceptable.
        data_version_check: Optional function that returns a "data version" (e.g., timestamp, hash).
                           If provided, cache is invalidated when the data version changes.
                           Function should be fast (e.g., query MAX(last_modified) from database).
    """
    def decorator(func: Callable) -> Callable:
        # Use function name as cache file name for persistence
        cache_file = f"{func.__name__}.cache"
        cache_instance = SimpleCache(ttl_seconds=ttl_seconds, cache_file=cache_file)
        
        # Store cache instance on the function for external access (e.g., for clearing)
        func._cache_instance = cache_instance
        
        # Log cache initialization for aggregate_stats
        if func.__name__ == "get_aggregate_stats":
            cache_path = cache_instance._get_cache_path()
            if cache_path and cache_path.exists():
                logger.info(f"[CACHE] {func.__name__}: Cache file exists: {cache_path.name}, cache size: {len(cache_instance.cache)}")
            else:
                logger.info(f"[CACHE] {func.__name__}: Cache file does not exist: {cache_file}")
        
        # Get or create lock for this function to prevent duplicate background refreshes
        with _background_refresh_locks_lock:
            if func.__name__ not in _background_refresh_locks:
                _background_refresh_locks[func.__name__] = threading.Lock()
                _background_refresh_status[func.__name__] = False
        refresh_lock = _background_refresh_locks[func.__name__]
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # If caching is globally disabled, just call the function directly
            if not CACHE_ENABLED:
                logger.debug(f"[CACHE] {func.__name__}: Caching disabled, calling function directly")
                return func(*args, **kwargs)
            
            # Create cache key from function name and arguments
            # Convert args/kwargs to strings for hashing
            args_str = str(args)
            kwargs_str = str(sorted(kwargs.items()))
            cache_key = f"{func.__name__}_{args_str}_{kwargs_str}"
            
            # Log function call BEFORE cache check (so it always shows)
            if func.__name__ == "get_aggregate_stats":
                logger.info(f"[AGGREGATE_STATS] get_aggregate_stats called for season={kwargs.get('season', args[0] if args else 'default')}")
            
            logger.debug(f"[CACHE] {func.__name__}: Checking cache for key: {cache_key[:80]}...")
            logger.debug(f"[CACHE] {func.__name__}: background_refresh={background_refresh}, refresh_lock.locked()={refresh_lock.locked()}")
            
            # Check cache first (fast, no DB query)
            # Only check data version if cache entry exists (to avoid expensive query on every request)
            cached_result = cache_instance.get(cache_key, data_version=None)  # First check without version
            
            # If cache entry exists, check data version to see if it's still valid
            current_data_version = None
            if cached_result is not None and data_version_check:
                # Only check data version if we have a cached entry (to avoid expensive query on cache miss)
                try:
                    current_data_version = data_version_check()
                    logger.info(f"[CACHE] {func.__name__}: Current data version: {current_data_version}")
                    
                    # Re-check cache with data version to invalidate if changed
                    cached_result = cache_instance.get(cache_key, data_version=current_data_version)
                except Exception as e:
                    logger.warning(f"[CACHE] {func.__name__}: Failed to get data version: {e}, proceeding without version check")
            stale_result = None
            
            if cached_result is not None:
                logger.info(f"[CACHE] {func.__name__}: Cache HIT (valid, not expired)")
            else:
                logger.info(f"[CACHE] {func.__name__}: Cache MISS (no valid entry found) - checking why...")
                # Log why cache miss occurred
                if cache_key in cache_instance.cache:
                    entry = cache_instance.cache[cache_key]
                    if len(entry) == 4:
                        _, timestamp, ttl, cached_data_version = entry
                        age = time.time() - timestamp
                        logger.info(f"[CACHE] {func.__name__}: Cache entry exists but invalid - age: {age:.1f}s, ttl: {ttl}s, expired: {age >= ttl}, data_version_match: {cached_data_version == current_data_version if current_data_version else 'N/A'}")
                        if current_data_version and cached_data_version != current_data_version:
                            logger.info(f"[CACHE] {func.__name__}: Data version mismatch - cached: {cached_data_version}, current: {current_data_version}")
                else:
                    logger.info(f"[CACHE] {func.__name__}: No cache entry found for key: {cache_key[:80]}...")
            
            if background_refresh:
                # For background refresh, also check for stale (expired) cache
                logger.debug(f"[CACHE] {func.__name__}: Checking for stale cache (background_refresh enabled)")
                if cache_key in cache_instance.cache:
                    entry = cache_instance.cache[cache_key]
                    if len(entry) == 3:
                        value, timestamp, ttl = entry
                        cached_data_version = None
                    else:
                        value, timestamp, ttl, cached_data_version = entry
                    age = time.time() - timestamp
                    logger.debug(f"[CACHE] {func.__name__}: Found cache entry - age={age:.1f}s, ttl={ttl}s, expired={age >= ttl}")
                    # Check if expired and data version matches (if provided)
                    data_version_matches = True
                    if current_data_version is not None and cached_data_version != current_data_version:
                        data_version_matches = False
                        logger.debug(f"[CACHE] {func.__name__}: Stale cache has different data version (cached: {cached_data_version}, current: {current_data_version}), cannot use as stale")
                    
                    if age >= ttl and data_version_matches:
                        # Cache is expired but exists and data version matches - use as stale result
                        stale_result = value
                        logger.info(f"[CACHE] {func.__name__}: Stale cache found (expired {age/3600:.1f}h ago, ttl={ttl/3600:.1f}h), will return stale and refresh in background")
                    else:
                        logger.debug(f"[CACHE] {func.__name__}: Cache entry is still valid (age < ttl)")
                else:
                    logger.debug(f"[CACHE] {func.__name__}: No cache entry found in cache dict")
            
            if cached_result is not None:
                # Cache hit (valid, not expired) - return immediately
                logger.debug(f"[CACHE] {func.__name__}: Returning valid cached result immediately")
                if background_refresh:
                    # Only refresh once per app session (not on every page load)
                    # Check if refresh has already been initiated this session
                    refresh_initiated = _background_refresh_initiated.get(func.__name__ + cache_key, False)
                    is_locked = refresh_lock.locked()
                    logger.debug(f"[CACHE] {func.__name__}: Checking if background refresh should start - lock.locked()={is_locked}, refresh_initiated={refresh_initiated}")
                    if not is_locked and not refresh_initiated:
                        # Mark as initiated for this session
                        _background_refresh_initiated[func.__name__ + cache_key] = True
                        logger.info(f"[CACHE] {func.__name__}: Marking refresh as initiated for this app session")
                        def refresh_in_background():
                            thread_id = threading.current_thread().ident
                            logger.info(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Background refresh thread started")
                            try:
                                logger.debug(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Setting refresh status to True")
                                _background_refresh_status[func.__name__] = True
                                logger.info(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Calling function to calculate fresh data...")
                                logger.info(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: About to call func(*args={args}, **kwargs={kwargs})")
                                start_time = time.time()
                                result = func(*args, **kwargs)
                                logger.info(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Function call completed, result received")
                                calc_time = time.time() - start_time
                                logger.info(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Function completed in {calc_time:.2f}s, result size: {len(str(result))} chars")
                                
                                logger.debug(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Caching result...")
                                # Get data version for this result
                                result_data_version = None
                                if data_version_check:
                                    try:
                                        result_data_version = data_version_check()
                                    except Exception as e:
                                        logger.warning(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Failed to get data version for cache: {e}")
                                
                                if dynamic_ttl:
                                    actual_ttl = dynamic_ttl(result)
                                    logger.debug(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Using dynamic TTL: {actual_ttl}s")
                                    cache_instance.set(cache_key, result, ttl=actual_ttl, data_version=result_data_version)
                                else:
                                    logger.debug(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Using default TTL: {ttl_seconds}s")
                                    cache_instance.set(cache_key, result, data_version=result_data_version)
                                
                                if func.__name__ == "get_aggregate_stats":
                                    logger.debug(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Saving cache to disk...")
                                    cache_instance.save()
                                    logger.info(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Background refresh complete - cache updated and saved to disk (TTL: {ttl_seconds/3600:.1f}h)")
                                else:
                                    logger.debug(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Background refresh complete")
                            except Exception as e:
                                logger.error(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Background refresh FAILED: {e}", exc_info=True)
                            finally:
                                logger.debug(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Setting refresh status to False and releasing lock")
                                _background_refresh_status[func.__name__] = False
                                refresh_lock.release()
                                logger.debug(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Lock released, thread exiting")
                        
                        # Try to acquire lock (non-blocking check) - only if not already initiated this session
                        if not refresh_initiated:
                            logger.debug(f"[CACHE] {func.__name__}: Attempting to acquire refresh lock (non-blocking)...")
                            if refresh_lock.acquire(blocking=False):
                                logger.info(f"[CACHE] {func.__name__}: Lock acquired, starting background refresh thread")
                                thread = threading.Thread(target=refresh_in_background, daemon=True)
                                thread.start()
                                logger.debug(f"[CACHE] {func.__name__}: Background refresh thread started (thread ID: {thread.ident})")
                            else:
                                logger.debug(f"[CACHE] {func.__name__}: Lock already held, background refresh already in progress, skipping")
                        else:
                            logger.debug(f"[CACHE] {func.__name__}: Refresh already initiated this session, skipping")
                else:
                    logger.debug(f"[CACHE] {func.__name__}: Background refresh disabled or lock already held, not starting refresh")
                
                if DEBUG_MODE:
                    logger.debug(f"[CACHE] {func.__name__}: Cache HIT - returning cached result (key: {cache_key[:80]}...)")
                else:
                    if func.__name__ == "get_aggregate_stats":
                        logger.info(f"[CACHE] {func.__name__}: Cache HIT - using cached data from disk (24h TTL)")
                return cached_result
            
            if stale_result is not None:
                # Stale cache exists - return it immediately and refresh in background
                logger.info(f"[CACHE] {func.__name__}: Returning stale cache immediately, starting background refresh")
                # Check if refresh has already been initiated this session
                refresh_initiated = _background_refresh_initiated.get(func.__name__ + cache_key, False)
                is_locked = refresh_lock.locked()
                logger.debug(f"[CACHE] {func.__name__}: Checking if stale refresh should start - lock.locked()={is_locked}, refresh_initiated={refresh_initiated}")
                if not is_locked and not refresh_initiated:
                    # Mark as initiated for this session
                    _background_refresh_initiated[func.__name__ + cache_key] = True
                    logger.info(f"[CACHE] {func.__name__}: Marking stale refresh as initiated for this app session")
                def refresh_in_background():
                    thread_id = threading.current_thread().ident
                    logger.info(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Background refresh thread started (stale cache was returned)")
                    try:
                        logger.debug(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Setting refresh status to True")
                        _background_refresh_status[func.__name__] = True
                        logger.info(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Calling function to calculate fresh data (replacing stale cache)...")
                        start_time = time.time()
                        result = func(*args, **kwargs)
                        calc_time = time.time() - start_time
                        logger.info(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Function completed in {calc_time:.2f}s, result size: {len(str(result))} chars")
                        
                        logger.debug(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Caching fresh result...")
                        # Get data version for this result
                        result_data_version = None
                        if data_version_check:
                            try:
                                result_data_version = data_version_check()
                            except Exception as e:
                                logger.warning(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Failed to get data version for cache: {e}")
                        
                        if dynamic_ttl:
                            actual_ttl = dynamic_ttl(result)
                            logger.debug(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Using dynamic TTL: {actual_ttl}s")
                            cache_instance.set(cache_key, result, ttl=actual_ttl, data_version=result_data_version)
                        else:
                            logger.debug(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Using default TTL: {ttl_seconds}s")
                            cache_instance.set(cache_key, result, data_version=result_data_version)
                        
                        if func.__name__ == "get_aggregate_stats":
                            logger.debug(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Saving cache to disk...")
                            cache_instance.save()
                            logger.info(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Background refresh complete - stale cache replaced and saved to disk (TTL: {ttl_seconds/3600:.1f}h)")
                        else:
                            logger.debug(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Background refresh complete")
                    except Exception as e:
                        logger.error(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Background refresh FAILED: {e}", exc_info=True)
                    finally:
                        logger.debug(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Setting refresh status to False and releasing lock")
                        _background_refresh_status[func.__name__] = False
                        refresh_lock.release()
                        logger.debug(f"[CACHE] [THREAD-{thread_id}] {func.__name__}: Lock released, thread exiting")
                
                # Start background refresh if not already in progress and not already initiated this session
                if not refresh_initiated:
                    logger.debug(f"[CACHE] {func.__name__}: Attempting to acquire refresh lock for stale cache refresh (non-blocking)...")
                    if refresh_lock.acquire(blocking=False):
                        logger.info(f"[CACHE] {func.__name__}: Lock acquired, starting background refresh thread for stale cache")
                        thread = threading.Thread(target=refresh_in_background, daemon=True)
                        thread.start()
                        logger.debug(f"[CACHE] {func.__name__}: Background refresh thread started (thread ID: {thread.ident})")
                    else:
                        logger.debug(f"[CACHE] {func.__name__}: Lock already held, background refresh already in progress, skipping")
                else:
                    logger.debug(f"[CACHE] {func.__name__}: Refresh already initiated this session, skipping")
                
                logger.debug(f"[CACHE] {func.__name__}: Returning stale cache result to caller")
                return stale_result
            
            # Cache miss - function will be called to calculate fresh (blocking)
            logger.info(f"[CACHE] {func.__name__}: Cache MISS - no valid or stale cache found, calculating fresh (blocking)")
            if func.__name__ == "get_aggregate_stats":
                cache_path = cache_instance._get_cache_path()
                if cache_path and cache_path.exists():
                    logger.info(f"[CACHE] {func.__name__}: Cache file exists but key not found or expired (file: {cache_path.name}, key: {cache_key[:60]}...)")
                else:
                    logger.info(f"[CACHE] {func.__name__}: No cache file found, calculating fresh data (this may take a while)")
            elif DEBUG_MODE:
                logger.debug(f"[CACHE] {func.__name__}: Cache MISS - calculating fresh (key: {cache_key[:80]}...)")
            
            # Call function and cache result
            logger.debug(f"[CACHE] {func.__name__}: Calling function to calculate result (blocking call)...")
            start_time = time.time()
            result = func(*args, **kwargs)
            calc_time = time.time() - start_time
            logger.info(f"[CACHE] {func.__name__}: Function completed in {calc_time:.2f}s, result size: {len(str(result))} chars")
            
            # Use dynamic TTL if provided, otherwise use default
            logger.debug(f"[CACHE] {func.__name__}: Caching result...")
            # Get data version for this result
            result_data_version = None
            if data_version_check:
                try:
                    result_data_version = data_version_check()
                    logger.debug(f"[CACHE] {func.__name__}: Data version for cached result: {result_data_version}")
                except Exception as e:
                    logger.warning(f"[CACHE] {func.__name__}: Failed to get data version for cache: {e}")
            
            if dynamic_ttl:
                actual_ttl = dynamic_ttl(result)
                logger.debug(f"[CACHE] {func.__name__}: Using dynamic TTL: {actual_ttl}s")
                cache_instance.set(cache_key, result, ttl=actual_ttl, data_version=result_data_version)
            else:
                logger.debug(f"[CACHE] {func.__name__}: Using default TTL: {ttl_seconds}s")
                cache_instance.set(cache_key, result, data_version=result_data_version)
            
            # Force save immediately for expensive calculations (want to persist)
            # Save for aggregate_stats and list_games (both are expensive and frequently accessed)
            if func.__name__ in ("get_aggregate_stats", "list_games"):
                logger.debug(f"[CACHE] {func.__name__}: Saving cache to disk immediately...")
                cache_instance.save()
                logger.info(f"[CACHE] {func.__name__}: Cache saved to disk (TTL: {ttl_seconds/3600:.1f}h)")
            
            logger.debug(f"[CACHE] {func.__name__}: Returning fresh calculated result")
            return result
        return wrapper
    return decorator

