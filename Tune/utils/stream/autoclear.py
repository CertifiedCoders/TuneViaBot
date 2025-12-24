# Authored By Certified Coders © 2025
import os

from config import autoclean


async def auto_clean(popped):
    try:
        if not popped or not isinstance(popped, dict):
            return
        
        rem = popped.get("file")
        if not rem or not isinstance(rem, str):
            return
        
        if rem in autoclean:
            try:
                autoclean.remove(rem)
            except (ValueError, AttributeError):
                pass
        
        if autoclean.count(rem) == 0:
            if "vid_" in rem or "live_" in rem or "index_" in rem:
                return
            
            if os.path.exists(rem) and os.path.isfile(rem):
                try:
                    os.remove(rem)
                except (OSError, PermissionError, FileNotFoundError):
                    pass
    except Exception:
        pass
