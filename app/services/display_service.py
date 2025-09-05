# display_service.py

from app.models import Display, SceneAssignment  # Adjust the import based on your project structure
from app.database import db  # Adjust the import based on your project structure

def get_display_by_id(display_id: str):
    """Fetch a display by its ID."""
    # Example: If you store displays in a list or DB, search for the ID
    # Replace this with your actual data access logic
    from ..data import displays  # adjust import as needed
    for display in displays:
        if display.get("id") == display_id:
            return display
    return None

def get_scene_assignment_for_display(display_id: str):
    """Fetch the scene assignment for a display."""
    # Replace with your actual data access logic
    # Example: assignment = db.query(SceneAssignment).filter(SceneAssignment.display_id == display_id).first()
    # if assignment: return {"scene_id": assignment.scene_id, "assigned_at": assignment.assigned_at}
    pass  # implement