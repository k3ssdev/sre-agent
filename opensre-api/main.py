import sys
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

sys.path.append('./opensre')
from core.agent_harness import AgentSession

app = FastAPI(title="OpenSRE Microservice")

class SREQuery(BaseModel):
    mensaje: str

@app.post("/investigar")
async def investigar_incidente(query: SREQuery):
    try:
        # Iniciamos la sesión permitiendo que el agente descubra las herramientas del entorno
        session = AgentSession.start()
        
        # Le pasamos la consulta del usuario
        result = session.chat(query.mensaje)
        
        if result.answered:
            return {"status": "ok", "respuesta": result.primary_response_text}
        else:
            return {"status": "incompleto", "respuesta": f"⚠️ Investigación no concluyente:\n`{str(result)}`"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)