"""
PTS Manager abstraction layer

This module provides simplified access to PTS (Position Token for Sequence) values,
relying on the central session_manager for actual state persistence.
"""

import logging
from app import session_manager # Assuming session_manager is in the same 'app' package

logger = logging.getLogger(__name__)

def get_pts():
    """
    Retrieve the current PTS value from the application state.

    Returns:
        int: The stored PTS value or 0 if not found or on error.
    """
    try:
        state = session_manager.load_app_state()
        pts = state.get("pts", 0)
        # Ensure pts is an integer, as load_app_state should already do this.
        # This is an additional safeguard or clarification.
        if not isinstance(pts, int):
            logger.warning(f"PTS value from state was not an int: {pts}. Returning 0.")
            return 0
        logger.debug(f"Retrieved PTS: {pts} from app_state")
        return pts
    except Exception as e:
        logger.error(f"Error retrieving PTS from app_state: {e}")
        return 0

def update_pts(new_pts_value):
    """
    Update the PTS value in the application state.

    Args:
        new_pts_value (int): The new PTS value to save.
    """
    if not isinstance(new_pts_value, int):
        logger.error(f"Invalid PTS value provided to update_pts: {new_pts_value}. Must be an integer.")
        return

    try:
        current_state = session_manager.load_app_state()
        current_state["pts"] = new_pts_value
        session_manager.save_app_state(current_state)
        logger.debug(f"Updated PTS to: {new_pts_value} in app_state")
    except Exception as e:
        logger.error(f"Error updating PTS in app_state: {e}")

# For compatibility if other parts of the code were using load_pts/save_pts directly
# and expected a channel_username argument, though it's now ignored.
# Consider removing these if all callers are updated to use get_pts() and update_pts(value).
def load_pts(channel_username=None): # channel_username is ignored
    """Alias for get_pts for backward compatibility. Channel username is ignored."""
    if channel_username:
        logger.debug(f"load_pts called with channel_username '{channel_username}', which is ignored.")
    return get_pts()

def save_pts(new_pts_value, channel_username=None): # channel_username is ignored
    """Alias for update_pts for backward compatibility. Channel username is ignored."""
    if channel_username: # channel_username is second arg in old save_pts_to_file
        logger.debug(f"save_pts called with channel_username '{channel_username}', which is ignored.")
    update_pts(new_pts_value) 