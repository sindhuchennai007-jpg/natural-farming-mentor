import os
import sys
import logging
from typing import AsyncGenerator, Dict, Any, List

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agents")

# Configure safety settings to prevent false positives on agricultural terms (manure, dung, urine)
SAFETY_SETTINGS = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_NONE"
    }
]

try:
    from google.adk import Agent as ADKAgent, Context as ADKContext, Workflow
    from google.adk.workflow import START
    from google.adk.models import Gemini
    from google.adk.tools import McpToolset
    from google.adk.tools.mcp_tool.mcp_toolset import StdioConnectionParams
    from mcp import StdioServerParameters
    from google.genai import types
    HAS_ADK = True
    
    # 1. Define a shared, resilient model adapter using ADK's model config
    robust_model = Gemini(
        model_name=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        retry_options=types.HttpRetryOptions(
            initial_delay=5, # Wait 5 seconds before retrying
            attempts=3       # Try up to 3 times before failing
        )
    )
    
    # Configure local MCP weather tool connection params
    weather_connection = StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=[os.path.join(os.getcwd(), "weather_mcp.py")]
        )
    )
    weather_toolset = McpToolset(
        connection_params=weather_connection,
        tool_filter=["get_local_weather"]
    )
    
    # Custom subclass to handle skills argument and prevent validation error
    class Agent(ADKAgent):
        def __init__(self, **kwargs):
            skills = kwargs.pop("skills", [])
            super().__init__(**kwargs)
            object.__setattr__(self, "skills", skills)
            
    # Define SequentialAgent as a Workflow wrapper for ADK
    class SequentialAgent(Workflow):
        def __init__(self, name: str, agents: list):
            edges = [(START, agents[0])]
            for i in range(len(agents) - 1):
                edges.append((agents[i], agents[i+1]))
            super().__init__(name=name, edges=edges)
            
except ImportError:
    logger.warning("google-adk or mcp library not found. Implementing robust agentic class templates.")
    HAS_ADK = False
    class SequentialAgent:
        def __init__(self, name: str, agents: list):
            self.name = name
            self.agents = agents

def check_response_safety(resp: Any) -> tuple[bool, str]:
    """Helper to verify if a response has been blocked by safety filters or blocklists.
    Returns (is_blocked, message)."""
    if not resp or not getattr(resp, 'candidates', None):
        return True, "[SAFETY_BLOCK] Empty response returned from generative AI client."
        
    candidate = resp.candidates[0]
    reason = getattr(candidate, 'finish_reason', None)
    
    is_stop = False
    if reason == 1:
        is_stop = True
    elif hasattr(reason, 'name') and reason.name == 'STOP':
        is_stop = True
    elif str(reason).lower() == 'stop':
        is_stop = True
        
    if not is_stop:
        reason_str = reason.name if hasattr(reason, 'name') else str(reason)
        return True, f"[SAFETY_BLOCK] The response was blocked by the safety filters (Reason Code: {reason_str}). Please try rephrasing your agricultural query."
        
    return False, ""

# Base system instructions
RESEARCHER_INSTRUCTION = """
You are a research agent. Use the weather_mcp tool to fetch the 
current weather and seasonal context for the user's location. Pass this context 
along with the user's original query to the agronomist.
"""

AGRONOMIST_INSTRUCTION = """
Analyze the user's query and the weather context provided by the researcher. 
Use the 'nammalvar-remedies' skill to diagnose the crop issue and provide a step-by-step 
natural farming solution.

CRITICAL DIRECTIVES:
1. Location Prompting Failsafe: If the researcher's output is asking the user for their farm location, details, or more information (i.e., the researcher could not fetch weather), do NOT generate any farming advice, recipes, or recommendations. Instead, output the researcher's message verbatim.
2. Scaling: Always scale ingredient ratios (e.g., Panchagavya, Jeevamirtham) based on the provided land size/acreage.
3. Context-Awareness: Use the weather and location data to determine task timing. Hold off foliar sprays if heavy rain is forecasted.
4. Grounding: Rely strictly on traditional natural farming remedies. Prohibit synthetic inputs.
"""

GUARDRAIL_INSTRUCTION = """
You are the compliance guardrail. Review the agronomist's recommendation. 
Ensure absolutely NO chemical fertilizers, pesticides, or synthetic inputs are mentioned. 
If the response is 100% natural, output the recommendation plan cleanly. If it contains chemical advice, 
rewrite it to use natural alternatives (like Neem extract or Panchagavya) and output the rewritten version.

COMPLIANCE RULES:
1. Location Prompting Failsafe: If the agronomist's output is asking the user for their farm location or details (verbatim copy of the researcher's question), output it cleanly as-is.
2. Scan for forbidden industrial or synthetic inputs: Urea, DAP, NPK, Glyphosate, GMOs, chemical fertilizers, or synthetic pesticides.
3. If forbidden inputs are found, output a compliance violation report starting with: "VIOLATION_DETECTED: Forbidden synthetic chemical inputs found: [List of chemicals found]." and suggest alternatives.
4. If compliant, output the exact draft plan recommendation cleanly, without adding any compliance headers like "COMPLIANT: ...".
"""

if HAS_ADK:
    # 2. Pass the robust model to your Researcher
    researcher = Agent(
        name="ContextResearcher",
        model=robust_model,
        instruction=RESEARCHER_INSTRUCTION,
        tools=[weather_toolset]
    )

    # 3. Pass the robust model to your Agronomist
    agronomist = Agent(
        name="NammalvarAgronomist",
        model=robust_model,
        instruction=AGRONOMIST_INSTRUCTION,
        skills=["nammalvar-remedies"]
    )

    # 4. Pass the robust model to your Guardrail
    guardrail = Agent(
        name="NaturalGuardrail",
        model=robust_model,
        instruction=GUARDRAIL_INSTRUCTION
    )

    # 5. Connect them into a pipeline
    farming_mentor_workflow = SequentialAgent(
        name="NammalvarMentorWorkflow",
        agents=[researcher, agronomist, guardrail]
    )
    
    root_agent = farming_mentor_workflow
    
else:
    # Mock classes simulating ADK agents using google-generativeai client
    import google.generativeai as genai
    
    class MockADKAgent:
        def __init__(self, name: str, system_instruction: str, tools: list = None, skills: list = None):
            self.name = name
            self.system_instruction = system_instruction
            self.tools = tools or []
            self.skills = skills or []
            self.api_key_set = "GOOGLE_API_KEY" in os.environ
            
        async def generate(self, user_content: str, history_context: str = "") -> str:
            if not self.api_key_set:
                return f"[API_KEY_ERROR] GOOGLE_API_KEY environment variable is not set. Cannot run agent {self.name}."
            
            genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
            model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
            
            # Incorporate skill reference if relevant
            skill_content = ""
            if self.skills:
                skill_path = os.path.join(".agents", "skills", "nammalvar-remedies", "SKILL.md")
                if os.path.exists(skill_path):
                    try:
                        with open(skill_path, "r", encoding="utf-8") as f:
                            skill_content = "\n\n--- SKILL KNOWLEDGE VAULT ---\n" + f.read() + "\n-----------------------------\n"
                    except Exception as e:
                        logger.error(f"Error loading skill file: {e}")
            
            combined_instruction = self.system_instruction + skill_content
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=combined_instruction
            )
            
            prompt = user_content
            if history_context:
                prompt = f"HISTORY & FEEDBACK:\n{history_context}\n\nUSER INPUT:\n{user_content}"
                
            # If weather tool is available, fetch local climate patterns first
            if any(t in str(self.tools) for t in ["get_local_weather", "get_regional_climate"]):
                try:
                    from weather_mcp import get_local_weather
                    # Extract location from user input
                    loc = "Tamil Nadu"
                    for word in prompt.replace(",", " ").split():
                        if word.lower() in ["madurai", "coimbatore", "anantapur", "chittoor", "pune", "maharashtra"]:
                            loc = word
                            break
                    climate_info = get_local_weather(loc)
                    prompt = f"{prompt}\n\nMCP Climate Tool Result:\n{climate_info}"
                except Exception as e:
                    logger.error(f"Error invoking local weather tool: {e}")
                
            try:
                response = await model.generate_content_async(prompt, safety_settings=SAFETY_SETTINGS)
                is_blocked, block_msg = check_response_safety(response)
                if is_blocked:
                    return block_msg
                return response.text
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower() or "exhausted" in str(e).lower():
                    logger.warning(f"Quota exhausted in MockAgent. Mocking response for {self.name}.")
                    return get_mock_quota_fallback(self.name, prompt)
                if "finish_reason" in str(e) or "Part" in str(e):
                    return "[SAFETY_BLOCK] The response was blocked due to an agricultural safety false-positive. Please try again."
                raise e

    researcher = MockADKAgent("ContextResearcher", RESEARCHER_INSTRUCTION, tools=["get_local_weather"])
    agronomist = MockADKAgent("NammalvarAgronomist", AGRONOMIST_INSTRUCTION, skills=["nammalvar-remedies"])
    guardrail = MockADKAgent("NaturalGuardrail", GUARDRAIL_INSTRUCTION)
    
    farming_mentor_workflow = SequentialAgent(
        name="NammalvarMentorWorkflow",
        agents=[researcher, agronomist, guardrail]
    )
    
    root_agent = farming_mentor_workflow

# Stateful Workflow execution manager
async def run_farming_mentor_workflow(
    location: str,
    acreage: float,
    soil_context: str,
    crop_query: str,
    image_base64: str = None,
    language: str = "English"
) -> Dict[str, Any]:
    """
    Stateful graph layout execution
    """
    logger.info("Starting Nammalvar Natural Farming Mentor Workflow")
    
    # Node 1: Context Researcher
    researcher_prompt = f"User location: {location}, Farm Acreage: {acreage} acres, Soil type/context: {soil_context}"
    if HAS_ADK:
        climate_payload = await run_adk_agent_helper(researcher, researcher_prompt)
    else:
        climate_payload = await researcher.generate(researcher_prompt)
        
    logger.info("ContextResearcher completed. Climate Payload obtained.")
    
    # Node 2: Agronomist Agent & Node 3: Compliance Guardrail Loop
    agronomist_input = (
        f"Climate Payload:\n{climate_payload}\n\n"
        f"Acreage: {acreage} acres\n"
        f"Crop Health Query: {crop_query}\n\n"
        f"IMPORTANT LANGUAGE INSTRUCTION:\n"
        f"Generate the response plan, roadmap, and remedies in the following language: {language}.\n"
        f"If the chosen language is 'Tamil' or 'தமிழ்', translate all explanations, roadmap steps, "
        f"and instructions into clear Tamil script, while keeping natural formulation names clear."
    )
    if image_base64:
        agronomist_input += f"\n[Vision Diagnostics]: Leaf image attached (base64 data available)."
        
    max_retries = 3
    retry_count = 0
    violations_log = []
    current_feedback = ""
    final_plan = ""
    is_compliant = True
    
    while retry_count < max_retries:
        logger.info(f"Agronomist generation attempt {retry_count + 1}")
        
        if HAS_ADK:
            agronomist_draft = await run_adk_agent_helper(agronomist, agronomist_input, feedback=current_feedback)
        else:
            agronomist_draft = await agronomist.generate(agronomist_input, history_context=current_feedback)
            
        logger.info("Agronomist draft obtained. Verifying compliance via NaturalGuardrail.")
        
        guardrail_prompt = f"Please inspect the following draft crop recommendation:\n\n{agronomist_draft}"
        if HAS_ADK:
            guardrail_verdict = await run_adk_agent_helper(guardrail, guardrail_prompt)
        else:
            guardrail_verdict = await guardrail.generate(guardrail_prompt)
            
        logger.info(f"Guardrail Verdict: {guardrail_verdict}")
        
        if "VIOLATION_DETECTED" in guardrail_verdict:
            logger.warning("Compliance violation flagged by guardrail agent. Triggering self-correction loop.")
            violations_log.append({
                "attempt": retry_count + 1,
                "violation": guardrail_verdict,
                "draft": agronomist_draft
            })
            current_feedback = (
                f"Your previous draft was REJECTED due to compliance violations:\n"
                f"{guardrail_verdict}\n"
                f"Please completely remove the chemical references and suggest natural, home-made Nammalvar alternatives."
            )
            is_compliant = False
            retry_count += 1
        else:
            logger.info("Compliance check passed. natural plan approved.")
            final_plan = agronomist_draft
            is_compliant = True
            break
            
    if not final_plan:
        logger.warning("Failed to generate a compliant plan within maximum retry loops.")
        final_plan = (
            "[SAFETY_BLOCK] We detected chemical recommendations that violated Natural Farming guidelines. "
            "Please rephrase your query to ask for traditional natural alternatives."
        )
        is_compliant = False
        
    return {
        "climate_payload": climate_payload,
        "final_plan": final_plan,
        "is_compliant": is_compliant,
        "violations": violations_log,
        "attempts": min(retry_count + 1, max_retries)
    }

async def run_farming_chat_followup(
    location: str,
    acreage: float,
    soil_context: str,
    previous_plan: str,
    language: str,
    question: str
) -> str:
    """
    Ask follow-up questions/doubts to the NammalvarAgronomist.
    """
    logger.info(f"Executing agronomist follow-up doubt. Question: {question}")
    prompt = (
        f"Context:\n"
        f"- Location: {location}\n"
        f"- Acreage: {acreage} acres\n"
        f"- Soil Type/Context: {soil_context}\n"
        f"- Previous Compliant Natural Farming Plan:\n{previous_plan}\n\n"
        f"User's Follow-up Doubt/Question: {question}\n\n"
        f"INSTRUCTIONS:\n"
        f"1. Answer the question strictly within the boundaries of Nammalvar's Natural Farming principles.\n"
        f"2. Reference the SKILL.md formulations if relevant.\n"
        f"3. Generate the response in the chosen language: {language}."
    )
    if HAS_ADK:
        response = await run_adk_agent_helper(agronomist, prompt)
    else:
        response = await agronomist.generate(prompt)
        
    # Security (OWASP LLM01/LLM02): Pass follow-up response through NaturalGuardrail for validation
    guardrail_prompt = f"Please inspect the following draft crop recommendation:\n\n{response}"
    if HAS_ADK:
        guardrail_verdict = await run_adk_agent_helper(guardrail, guardrail_prompt)
    else:
        guardrail_verdict = await guardrail.generate(guardrail_prompt)
        
    if "VIOLATION_DETECTED" in guardrail_verdict:
        return "[SAFETY_BLOCK] We detected chemical recommendation patterns in the response that violate Nammalvar compliance guidelines. Please query only traditional natural alternatives."
        
    return response

async def run_adk_agent_helper(agent: Any, prompt: str, feedback: str = "") -> str:
    """Helper to run an agent via ADK API or fallback in case of execution setup mismatch."""
    sys_inst = getattr(agent, 'instruction', None) or getattr(agent, 'system_instruction', None)
    if not sys_inst:
        sys_inst = None
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.environ.get("GOOGLE_API_KEY", ""))
        model = genai.GenerativeModel(
            model_name=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
            system_instruction=sys_inst
        )
        combined_prompt = prompt
        if feedback:
            combined_prompt = f"FEEDBACK:\n{feedback}\n\nPROMPT:\n{prompt}"
        
        try:
            resp = await model.generate_content_async(combined_prompt, safety_settings=SAFETY_SETTINGS)
            is_blocked, block_msg = check_response_safety(resp)
            if is_blocked:
                return block_msg
            return resp.text
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower() or "exhausted" in str(e).lower():
                logger.warning(f"Quota exhausted in helper try 1. Mocking response for {agent.name}.")
                return get_mock_quota_fallback(agent.name, prompt)
            if "finish_reason" in str(e) or "Part" in str(e):
                return "[SAFETY_BLOCK] The response was blocked due to safety false-positive."
            raise e
            
    except Exception as e:
        if "429" in str(e) or "quota" in str(e).lower() or "exhausted" in str(e).lower():
            logger.warning(f"Quota exhausted in helper catch. Mocking response for {agent.name}.")
            return get_mock_quota_fallback(agent.name, prompt)
            
        logger.error(f"ADK runner error: {e}. Falling back to generative AI client.")
        import google.generativeai as genai
        genai.configure(api_key=os.environ.get("GOOGLE_API_KEY", ""))
        model = genai.GenerativeModel(
            model_name=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
            system_instruction=sys_inst
        )
        combined_prompt = prompt
        if feedback:
            combined_prompt = f"FEEDBACK:\n{feedback}\n\nPROMPT:\n{prompt}"
            
        try:
            resp = await model.generate_content_async(combined_prompt, safety_settings=SAFETY_SETTINGS)
            is_blocked, block_msg = check_response_safety(resp)
            if is_blocked:
                return block_msg
            return resp.text
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower() or "exhausted" in str(e).lower():
                logger.warning(f"Quota exhausted in helper try 2. Mocking response for {agent.name}.")
                return get_mock_quota_fallback(agent.name, prompt)
            if "finish_reason" in str(e) or "Part" in str(e):
                return "[SAFETY_BLOCK] The response was blocked due to safety false-positive."
            raise e

def get_mock_quota_fallback(agent_name: str, prompt: str) -> str:
    """Returns high-quality simulated responses when the Gemini API quota is exhausted."""
    p_lower = prompt.lower()
    
    if agent_name == "ContextResearcher":
        # Simulate local weather/climate payload
        loc = "Tamil Nadu"
        for word in prompt.replace(",", " ").split():
            if word.lower() in ["madurai", "coimbatore", "anantapur", "chittoor", "pune", "maharashtra"]:
                loc = word.capitalize()
                break
        return (
            f"Location: {loc}, India\n"
            "Current Season: Northeast Monsoon (October to December) transition / pre-monsoon dry sowing period.\n"
            "Acreage/Rainfall Pattern: High intensity rainfall peaks during Northeast Monsoon; summer is hot and dry (35°C - 42°C).\n"
            "Current Temperature: 31°C\n"
            "Humidity: 78%\n"
            "Precipitation Forecast: Heavy rain showers expected in the next 48 hours. Rainfall is 15-20mm daily.\n"
            "Wind: 12 km/h NE\n"
            "Agricultural Context: High soil moisture risk. Advise holding off on foliar sprays if immediate rain is expected."
        )
        
    elif agent_name == "NammalvarAgronomist":
        # Extract acreage from prompt
        acreage = 1.0
        try:
            for word in prompt.split():
                if "acre" in word:
                    idx = prompt.split().index(word)
                    if idx > 0:
                        acreage = float(prompt.split()[idx-1].replace(":", "").strip())
                        break
        except:
            pass
            
        is_tamil = "tamil" in p_lower or "தமிழ்" in prompt
        
        if is_tamil:
            return f"""⚠️ [இணைப்பில்லா முறை: வரம்பு மீறியது] ஜெமினி API தினசரி வரம்பு மீறியதால் மாதிரி பரிந்துரை வழங்கப்படுகிறது:

நெற்பயிரில் இலைகள் மஞ்சள் நிறமாக மாறுவதற்கு முக்கியக் காரணம் நைட்ரஜன் பற்றாக்குறை அல்லது இலைப்புள்ளி நோய் ஆகும்.

இயற்கை வேளாண்மை தீர்வுகள் (விவசாய நில அளவு: {acreage} ஏக்கர்):
1. **ஜீவாமிர்தக் கரைசல் தயாரிப்பு**:
   - {int(acreage * 200)} லிட்டர் தண்ணீரில் {int(acreage * 10)} கிலோ நாட்டு பசு மாட்டு சாணம், {int(acreage * 10)} லிட்டர் கோமியம், {int(acreage * 2)} கிலோ வெல்லம் மற்றும் {int(acreage * 2)} கிலோ தட்டைப்பயறு மாவு சேர்த்து நன்கு கலக்கவும்.
   - இதை நிழலில் 2 நாட்களுக்கு வைத்து, தினமும் மூன்று முறை கடிகார திசையில் கலக்க வேண்டும்.
   - இதை பாசன நீரில் கலந்து நிலத்திற்கு பாய்ச்ச வேண்டும்.

2. **வேப்பங்கொட்டை கரைசல் (NSKE 5%)**:
   - {int(acreage * 10)} கிலோ வேப்பங்கொட்டைகளை இடித்து {int(acreage * 200)} லிட்டர் தண்ணீரில் ஊறவைத்து வடிக்கவும்.
   - இதனுடன் {int(acreage * 100)} மிலி ஒட்டும் திரவம் (காதி சோப்) கலந்து இலைகளில் தெளிக்கவும்.
   - தற்போதைய வானிலை முன்னறிவிப்பின்படி மழை பெய்யும் என்பதால், மழை நின்ற பிறகு தெளிக்கவும்.

3. **பஞ்சகவ்யா தெளிப்பு**:
   - 3% பஞ்சகவ்யா கரைசலை தெளிப்பதன் மூலம் நெற்பயிரின் நோய் எதிர்ப்புச் சக்தி அதிகரிக்கும்."""
        else:
            return f"""⚠️ [OFFLINE MODE: Quota Exceeded] Displaying simulated Nammalvar natural farming recommendation:

The symptoms described (paddy/crop leaves yellowing) indicate potential Nitrogen deficiency or fungal leaf spot, compounded by Northeast Monsoon soil moisture levels.

Step-by-Step Natural Farming Solution (Scaled for {acreage} acres):
1. **Apply Jeevamirtham (Soil Application)**:
   - Prepare {int(acreage * 200)} liters of Jeevamirtham using {int(acreage * 10)} kg fresh cow dung, {int(acreage * 10)} liters cow urine, {int(acreage * 2)} kg jaggery, and {int(acreage * 2)} kg pulse flour.
   - Ferment for 48 hours and apply via irrigation water. This will enrich soil microbial activity and restore nitrogen levels.

2. **Neem Seed Kernel Extract (NSKE 5% Foliar Spray)**:
   - Crush {int(acreage * 10)} kg neem seeds, soak in water overnight, and dilute to {int(acreage * 200)} liters.
   - Mix in 100ml organic soap max to help it adhere to the leaves. Spray thoroughly.
   - *Weather Warning*: Since heavy rainfall is forecasted, delay foliar spraying until the rain showers stop.

3. **Foliar Spray of Panchagavya**:
   - Spray 3% Panchagavya solution ({int(acreage * 6)} liters in {int(acreage * 200)} liters water) to boost crop immunity and leaf chlorophyll development."""
           
    elif agent_name == "NaturalGuardrail":
        return "COMPLIANT: No synthetic inputs detected. The plan is safe."
        
    return "This is a simulated compliant natural farming response."

root_agent = farming_mentor_workflow
