import sys
from fastmcp import FastMCP
import logging

# Set up logging to stderr (avoiding stdout to not corrupt stdio protocol)
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("weather_mcp")

# Initialize FastMCP Server
mcp = FastMCP("Climate Data Server")

@mcp.tool()
def get_regional_climate(location: str) -> str:
    """
    Get regional climate, season, temperature, humidity, and rainfall patterns for a given location.
    
    Args:
        location: The user's farm location (e.g. 'Madurai, Tamil Nadu', 'Anantapur, Andhra Pradesh').
    """
    logger.info(f"Fetching climate data for location: {location}")
    
    loc_lower = location.lower()
    
    # Simulate realistic meteorological data for Tamil Nadu and neighboring regions
    if "tamil nadu" in loc_lower or "tn" in loc_lower or "madurai" in loc_lower or "coimbatore" in loc_lower or "chennai" in loc_lower:
        return (
            "Location: Tamil Nadu, India\n"
            "Current Season: Northeast Monsoon (October to December) transition / pre-monsoon dry sowing period.\n"
            "Acreage/Rainfall Pattern: High intensity rainfall peaks during Northeast Monsoon; summer is hot and dry (35°C - 42°C).\n"
            "Current Temperature: 31°C\n"
            "Humidity: 78%\n"
            "Precipitation Forecast: Heavy rain showers expected in the next 48 hours. Rainfall is 15-20mm daily.\n"
            "Wind: 12 km/h NE\n"
            "Agricultural Context: High soil moisture risk. Advise holding off on foliar sprays if immediate rain is expected."
        )
    elif "andhra" in loc_lower or "ap" in loc_lower or "anantapur" in loc_lower or "chittoor" in loc_lower:
        return (
            "Location: Andhra Pradesh, India\n"
            "Current Season: Southwest Monsoon transition / dry cropping season.\n"
            "Acreage/Rainfall Pattern: Semiarid region, erratic rainfall (500-700mm annually). Frequent dry spells.\n"
            "Current Temperature: 34°C\n"
            "Humidity: 55%\n"
            "Precipitation Forecast: Low to clear skies, no immediate rain forecast in next 7 days.\n"
            "Wind: 8 km/h NW\n"
            "Agricultural Context: Soil moisture preservation is critical. Advise mulching (Acchadana) and drip/alternate furrow irrigation (Whapasa) to minimize evaporation."
        )
    else:
        return (
            f"Location: {location}\n"
            "Current Season: General Tropical Season.\n"
            "Current Temperature: 30°C\n"
            "Humidity: 65%\n"
            "Precipitation Forecast: Moderate rain showers likely in afternoon (5mm).\n"
            "Wind: 10 km/h\n"
            "Agricultural Context: Maintain organic cover. Keep watch on rain patterns before applying liquid concoctions."
        )

@mcp.tool()
def get_local_weather(location: str) -> str:
    """
    Get local weather and seasonal context for the user's location.
    
    Args:
        location: The user's farm location (e.g. 'Madurai, Tamil Nadu').
    """
    logger.info(f"Fetching local weather for location: {location}")
    return get_regional_climate(location)

if __name__ == "__main__":
    mcp.run()
