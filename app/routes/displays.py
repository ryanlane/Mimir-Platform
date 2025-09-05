from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from ..models.display import Display  # adjust import as needed
from ..models.scene import Scene  # adjust import as needed
from ..services.display_service import get_display_by_id, get_scene_assignment_for_display  # adjust as needed

router = APIRouter()

@router.get("/displays/{display_id}", response_model=Display)
def get_display(display_id: str):
    """Get details for a specific display.

    Args:
        display_id (str): The display's unique identifier.

    Returns:
        Display: Display details.

    Raises:
        HTTPException: If display not found.
    """
    display = get_display_by_id(display_id)
    if not display:
        raise HTTPException(status_code=404, detail="Display not found")
    return display

@router.get("/displays/{display_id}/scene")
def get_display_scene_assignment(display_id: str):
    """Get the scene assignment for a display.

    Args:
        display_id (str): The display's unique identifier.

    Returns:
        dict: Scene assignment info.

    Raises:
        HTTPException: If display or assignment not found.
    """
    assignment = get_scene_assignment_for_display(display_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="No scene assignment found for this display")
    return JSONResponse(content=assignment)