import os
import sys

os.environ.setdefault("LLM_PROVIDER", "ollama")
os.environ.setdefault("OLLAMA_MODEL", "qwen2.5-coder:latest")
os.environ.setdefault("OLLAMA_HOST", "http://host.docker.internal:11434")

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# Ahora sí importamos la librería (leerá las variables que acabamos de forzar)
sys.path.append('./opensre')
from core.agent_harness import AgentSession

app = FastAPI(title="OpenSRE Microservice")

class SREQuery(BaseModel):
    mensaje: str

@app.post("/investigar")
async def investigar_incidente(query: SREQuery):
    try:
        session = AgentSession.start()
        result = session.chat(query.mensaje)
        
        if result.answered:
            return {"status": "ok", "respuesta": result.primary_response_text}
        else:
            return {"status": "incompleto", "respuesta": f"⚠️ Fallo interno del agente. Volcado:\n`{str(result)}`"}
            
    except Exception as e:
        print(f"ERROR CRITICO: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)