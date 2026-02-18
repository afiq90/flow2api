from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
import httpx

router = APIRouter()

@router.get("/ip.txt", response_class=PlainTextResponse)
async def get_ip_details(request: Request):
    # Get client IP, considering proxies
    client_ip = request.headers.get("x-forwarded-for")
    if client_ip:
        client_ip = client_ip.split(",")[0].strip()
    else:
        client_ip = request.client.host

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://ipapi.co/{client_ip}/json/", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                details = [
                    f"IP: {data.get('ip')}",
                    f"City: {data.get('city')}",
                    f"Region: {data.get('region')}",
                    f"Country: {data.get('country_name')}",
                    f"ASN: {data.get('asn')}",
                    f"Org: {data.get('org')}"
                ]
                return "\n".join(details)
    except Exception:
        pass
    
    return f"IP: {client_ip}\nDetails: Information unavailable"
