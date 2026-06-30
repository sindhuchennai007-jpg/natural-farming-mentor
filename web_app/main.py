import os
import sys
import base64
import logging
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

# Add parent directory to path to allow importing agentic_workflow and weather_mcp
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agentic_workflow.agent import run_farming_mentor_workflow, run_farming_chat_followup

app = FastAPI(title="Nammalvar Natural Farming Mentor")

# Ensure static and templates folders exist
os.makedirs("web_app/static/css", exist_ok=True)
os.makedirs("web_app/templates", exist_ok=True)

# Mount static files and initialize templates
app.mount("/static", StaticFiles(directory="web_app/static"), name="static")
templates = Jinja2Templates(directory="web_app/templates")

@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "result": None,
            "input_data": {
                "location": "Madurai, Tamil Nadu",
                "acreage": 1.0,
                "soil_context": "Red loam soil, high organic potential",
                "crop_query": "Sorghum leaves turning yellow with minor spots. How to fix naturally?"
            },
            "selected_language": "English"
        }
    )

@app.post("/diagnose", response_class=HTMLResponse)
async def handle_diagnosis(
    request: Request,
    location: str = Form(...),
    acreage: float = Form(...),
    soil_context: str = Form(...),
    crop_query: str = Form(...),
    language: str = Form("English"),
    image_file: UploadFile = File(None)
):
    logger.info(f"Received diagnosis request. Location: {location}, Acreage: {acreage}, Language: {language}")
    
    image_base64 = None
    if image_file and image_file.filename:
        try:
            # Security (OWASP Web A05): Limit file upload size to 5MB to prevent memory exhaustion Denial of Service (DoS)
            MAX_FILE_SIZE = 5 * 1024 * 1024
            content = await image_file.read()
            if len(content) > MAX_FILE_SIZE:
                logger.warning(f"Rejected upload: file size {len(content)} exceeds 5MB limit.")
                error_msg = "Image upload exceeded size limit. Maximum allowed size is 5MB."
                return templates.TemplateResponse(
                    request=request,
                    name="index.html",
                    context={
                        "result": None,
                        "input_data": {
                            "location": location,
                            "acreage": acreage,
                            "soil_context": soil_context,
                            "crop_query": crop_query
                        },
                        "selected_language": language,
                        "error": error_msg
                    }
                )
            
            # Security (OWASP Web A03): Restrict content types to only allow images to prevent malicious script uploads
            if image_file.content_type and not image_file.content_type.startswith("image/"):
                logger.warning(f"Rejected upload: invalid content-type '{image_file.content_type}'.")
                error_msg = "Invalid file type. Only image files (JPEG, PNG, GIF, WebP) are allowed."
                return templates.TemplateResponse(
                    request=request,
                    name="index.html",
                    context={
                        "result": None,
                        "input_data": {
                            "location": location,
                            "acreage": acreage,
                            "soil_context": soil_context,
                            "crop_query": crop_query
                        },
                        "selected_language": language,
                        "error": error_msg
                    }
                )
            
            if content:
                image_base64 = base64.b64encode(content).decode("utf-8")
                logger.info("Successfully read uploaded image and converted to base64.")
        except Exception as e:
            logger.error(f"Failed to read image file: {e}")
            error_msg = f"Failed to process uploaded image: {str(e)}"
            return templates.TemplateResponse(
                request=request,
                name="index.html",
                context={
                    "result": None,
                    "input_data": {
                        "location": location,
                        "acreage": acreage,
                        "soil_context": soil_context,
                        "crop_query": crop_query
                    },
                    "selected_language": language,
                    "error": error_msg
                }
            )
            
    error_msg = None
    workflow_output = None
    try:
        # Run stateful ADK-compliant workflow
        workflow_output = await run_farming_mentor_workflow(
            location=location,
            acreage=acreage,
            soil_context=soil_context,
            crop_query=crop_query,
            image_base64=image_base64,
            language=language
        )
        
        # Check if output contains a safety block message
        if "[SAFETY_BLOCK]" in workflow_output.get("final_plan", ""):
            error_msg = workflow_output["final_plan"].replace("[SAFETY_BLOCK]", "").strip()
            workflow_output = None
            
    except Exception as e:
        logger.error(f"Error executing agent workflow: {e}")
        error_msg = str(e)
        if "429" in error_msg or "quota" in error_msg.lower():
            error_msg = "Gemini API rate limit exceeded (5 requests per minute limit on free tier). Please wait 45 seconds and try again."
        elif "finish_reason" in error_msg or "Part" in error_msg:
            error_msg = "The agricultural context triggered a false-positive in Gemini's default safety filter. Please rephrase slightly."
        
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "result": workflow_output,
            "input_data": {
                "location": location,
                "acreage": acreage,
                "soil_context": soil_context,
                "crop_query": crop_query
            },
            "selected_language": language,
            "error": error_msg
        }
    )

@app.post("/chat", response_class=HTMLResponse)
async def handle_chat_followup(
    request: Request,
    location: str = Form(...),
    acreage: float = Form(...),
    soil_context: str = Form(...),
    final_plan: str = Form(...),
    climate_payload: str = Form(""),
    language: str = Form("English"),
    question: str = Form(...),
    chat_history: str = Form("")
):
    logger.info(f"Received chat follow-up question: {question} in {language}")
    
    error_msg = None
    answer = ""
    try:
        answer = await run_farming_chat_followup(
            location=location,
            acreage=acreage,
            soil_context=soil_context,
            previous_plan=final_plan,
            language=language,
            question=question
        )
        
        if "[SAFETY_BLOCK]" in answer:
            error_msg = answer.replace("[SAFETY_BLOCK]", "").strip()
            answer = "Sorry, that question could not be answered due to a safety false-positive."
            
    except Exception as e:
        logger.error(f"Error executing follow-up doubt query: {e}")
        error_msg = str(e)
        if "429" in error_msg or "quota" in error_msg.lower():
            error_msg = "Gemini API rate limit exceeded (5 requests per minute limit on free tier). Please wait 45 seconds and try again."
        else:
            error_msg = f"Error: {str(e)}"
        answer = "Error processing response."
        
    # Append to chat history
    new_chat_history = chat_history
    if new_chat_history:
        new_chat_history += "\n\n"
    new_chat_history += f"**User:** {question}\n\n**Mentor:** {answer}"
    
    result = {
        "climate_payload": climate_payload,
        "final_plan": final_plan,
        "is_compliant": True,
        "violations": [],
        "attempts": 1,
        "chat_history": new_chat_history
    }
    
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "result": result,
            "input_data": {
                "location": location,
                "acreage": acreage,
                "soil_context": soil_context,
                "crop_query": ""
            },
            "selected_language": language,
            "error": error_msg
        }
    )

# API JSON endpoint for programmatic client access
@app.post("/api/diagnose", response_class=JSONResponse)
async def api_diagnosis(
    location: str = Form(...),
    acreage: float = Form(...),
    soil_context: str = Form(...),
    crop_query: str = Form(...),
    language: str = Form("English"),
    image_file: UploadFile = File(None)
):
    image_base64 = None
    if image_file and image_file.filename:
        try:
            content = await image_file.read()
            image_base64 = base64.b64encode(content).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to read image file: {e}")
            
    try:
        workflow_output = await run_farming_mentor_workflow(
            location=location,
            acreage=acreage,
            soil_context=soil_context,
            crop_query=crop_query,
            image_base64=image_base64,
            language=language
        )
        return JSONResponse(content=workflow_output)
    except Exception as e:
        logger.error(f"API error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_app.main:app", host="0.0.0.0", port=8080, reload=True)
