# Authored By Certified Coders © 2025
import os

from config import autoclean


async def auto_clean(popped):
    try:
        if not popped or not isinstance(popped, dict):
            return
        rem = popped.get("file")
        if not rem:
            return
        
        if rem in autoclean:
            try:
                autoclean.remove(rem)
            except (ValueError, AttributeError):
                pass
        
        count = autoclean.count(rem) if hasattr(autoclean, 'count') else 0
        if count == 0:
            if isinstance(rem, str):
                if "vid_" in rem or "live_" in rem or "index_" in rem:
                    return
                if os.path.exists(rem) and os.path.isfile(rem):
                    try:
                        os.remove(rem)
                    except (OSError, PermissionError, FileNotFoundError):
                        pass
    except Exception:
        pass
