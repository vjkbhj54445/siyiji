import os
import subprocess
import json
from enum import Enum
from typing import Dict, Any

class FailureType(Enum):
    TIMEOUT = "timeout"
    NONZERO = "nonzero"
    EXCEPTION = "exception"

def execute_script(script_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    # 从manifest加载脚本元数据
    with open("/app/scripts/manifest.json") as f:
        manifest = json.load(f)
    
    if script_name not in manifest:
        raise ValueError(f"Script {script_name} not found in manifest")
    
    script_meta = manifest[script_name]
    working_dir = script_meta.get("working_dir", "/workspace")
    
    # 安全检查：工作目录限制
    if not os.path.abspath(working_dir).startswith("/workspace"):
        raise SecurityError("Working directory must be under /workspace")
    
    # 构建命令
    cmd = ["python", f"/workspace/{script_name}.py"]
    for k, v in parameters.items():
        cmd.extend([f"--{k}", str(v)])
    
    result = {
        "script_name": script_name,
        "parameters": parameters,
        "status": "running",
        "start_time": get_current_timestamp(),
        "failure_type": None
    }
    
    try:
        # 执行脚本
        process = subprocess.run(
            cmd,
            cwd=working_dir,
            timeout=300,  # 5分钟超时
            capture_output=True,
            text=True
        )
        
        if process.returncode == 0:
            result["status"] = "success"
            result["result_status"] = "success"
        else:
            result["status"] = "failed"
            result["result_status"] = "failure"
            result["failure_type"] = FailureType.NONZERO.value
            
    except subprocess.TimeoutExpired:
        result["status"] = "failed"
        result["result_status"] = "failure"
        result["failure_type"] = FailureType.TIMEOUT.value
        
    except Exception as e:
        result["status"] = "failed"
        result["result_status"] = "failure"
        result["failure_type"] = FailureType.EXCEPTION.value
        result["error_message"] = str(e)
        
    finally:
        result["end_time"] = get_current_timestamp()
        
        # 记录到数据库（通过API或直接DB操作）
        db.record_run(result)
        
    return result