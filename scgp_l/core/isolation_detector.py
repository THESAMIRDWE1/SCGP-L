"""Detect and test available sandboxing capabilities.

Does NOT assume sandbox is secure.
Tests concrete isolation properties.
Returns BLOCKED if properties cannot be verified.
"""

import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
import json


class IsolationDetector:
    """Test actual sandbox isolation properties."""
    
    def __init__(self):
        self.available_tools = {}
        self.tested_properties = {}
    
    def detect_available_tools(self) -> Dict[str, bool]:
        """Check which sandbox tools are available."""
        tools = ["bwrap", "firejail", "unshare"]
        for tool in tools:
            result = shutil.which(tool)
            self.available_tools[tool] = result is not None
        return self.available_tools
    
    def test_isolation_properties(self, sandbox_tool: str) -> Dict[str, Any]:
        """Test concrete isolation properties of sandbox tool.
        
        Returns dict with all test results.
        If ANY test fails to execute, return BLOCKED.
        """
        if sandbox_tool not in self.available_tools or not self.available_tools[sandbox_tool]:
            return {
                "layer": "RAW_OBSERVATION",
                "sandbox_tool": sandbox_tool,
                "available": False,
                "tested": False,
                "blocked": True,
                "reason": f"Tool {sandbox_tool} not found"
            }
        
        tmpdir = Path(tempfile.mkdtemp(prefix="scgpL_isolation_test_"))
        try:
            results = {
                "layer": "RAW_OBSERVATION",
                "sandbox_tool": sandbox_tool,
                "available": True,
                "timestamp": None,
                "test_results": {}
            }
            
            # Test 1: Can read files outside sandbox?
            results["test_results"]["read_external"] = self._test_read_external(tmpdir, sandbox_tool)
            
            # Test 2: Can access network?
            results["test_results"]["network_blocked"] = self._test_network_blocked(tmpdir, sandbox_tool)
            
            # Test 3: Can write outside sandbox?
            results["test_results"]["write_blocked"] = self._test_write_blocked(tmpdir, sandbox_tool)
            
            # Check if all tests executed successfully
            all_executed = all(
                t.get("executed", False) 
                for t in results["test_results"].values()
            )
            
            results["all_tests_executed"] = all_executed
            results["blocked"] = not all_executed
            
            if not all_executed:
                results["reason"] = "One or more sandbox tests failed to execute"
            else:
                # Check if isolation properties hold
                can_read = results["test_results"]["read_external"].get("can_read", True)
                network_blocked = results["test_results"]["network_blocked"].get("network_blocked", False)
                write_blocked = results["test_results"]["write_blocked"].get("write_blocked", False)
                
                results["isolation_verified"] = (not can_read) and network_blocked and write_blocked
                results["blocked"] = not results["isolation_verified"]
            
            return results
        
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
    
    def _test_read_external(self, tmpdir: Path, sandbox_tool: str) -> Dict[str, Any]:
        """Test: Can sandbox read files outside its directory?"""
        sentinel = Path(tempfile.mkstemp(prefix="scgpL_sentinel_")[1])
        sentinel.write_text("SCGP-L-SENTINEL-STRING-12345")
        
        test_script = tmpdir / "test_read.py"
        test_script.write_text(f"""
import sys
try:
    with open({str(sentinel)!r}, 'r') as f:
        content = f.read()
    if 'SCGP-L-SENTINEL' in content:
        print('CAN_READ_EXTERNAL')
    else:
        print('FILE_NOT_READABLE')
except Exception as e:
    print('FILE_NOT_ACCESSIBLE')
""")
        
        try:
            if sandbox_tool == "unshare":
                cmd = ["unshare", "-n", "python3", str(test_script)]
            elif sandbox_tool == "firejail":
                cmd = ["firejail", "--noprofile", "--quiet", "python3", str(test_script)]
            elif sandbox_tool == "bwrap":
                cmd = [
                    "bwrap", "--die-with-parent", "--unshare-net",
                    "--ro-bind", "/usr", "/usr",
                    "--ro-bind", "/bin", "/bin",
                    "--tmpfs", "/tmp",
                    "--bind", str(tmpdir), "/work",
                    "--chdir", "/work",
                    "--", "python3", "/work/test_read.py"
                ]
            else:
                return {
                    "executed": False,
                    "reason": f"Unknown sandbox tool: {sandbox_tool}"
                }
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            output = result.stdout.strip()
            return {
                "executed": True,
                "output": output,
                "can_read": "CAN_READ_EXTERNAL" in output
            }
        
        except subprocess.TimeoutExpired:
            return {"executed": False, "reason": "Timeout"}
        except Exception as e:
            return {"executed": False, "reason": str(e)}
        finally:
            sentinel.unlink(missing_ok=True)
    
    def _test_network_blocked(self, tmpdir: Path, sandbox_tool: str) -> Dict[str, Any]:
        """Test: Is network access blocked?"""
        test_script = tmpdir / "test_network.py"
        test_script.write_text("""
import socket
import sys
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    s.connect(('1.1.1.1', 80))
    print('NETWORK_ACCESSIBLE')
    s.close()
except Exception:
    print('NETWORK_BLOCKED')
""")
        
        try:
            if sandbox_tool == "unshare":
                cmd = ["unshare", "-n", "python3", str(test_script)]
            elif sandbox_tool == "firejail":
                cmd = ["firejail", "--net=none", "--quiet", "python3", str(test_script)]
            elif sandbox_tool == "bwrap":
                cmd = [
                    "bwrap", "--die-with-parent", "--unshare-net",
                    "--ro-bind", "/usr", "/usr",
                    "--ro-bind", "/bin", "/bin",
                    "--tmpfs", "/tmp",
                    "--bind", str(tmpdir), "/work",
                    "--chdir", "/work",
                    "--", "python3", "/work/test_network.py"
                ]
            else:
                return {"executed": False, "reason": f"Unknown sandbox: {sandbox_tool}"}
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            output = result.stdout.strip()
            return {
                "executed": True,
                "output": output,
                "network_blocked": "NETWORK_BLOCKED" in output
            }
        except subprocess.TimeoutExpired:
            return {"executed": False, "reason": "Timeout"}
        except Exception as e:
            return {"executed": False, "reason": str(e)}
    
    def _test_write_blocked(self, tmpdir: Path, sandbox_tool: str) -> Dict[str, Any]:
        """Test: Can sandbox write outside its directory?"""
        external_dir = Path(tempfile.mkdtemp(prefix="scgpL_external_"))
        test_script = tmpdir / "test_write.py"
        test_script.write_text(f"""
import sys
try:
    with open({str(external_dir / 'test.txt')!r}, 'w') as f:
        f.write('WRITE_SUCCEEDED')
    print('CAN_WRITE_EXTERNAL')
except Exception:
    print('WRITE_BLOCKED')
""")
        
        try:
            if sandbox_tool == "unshare":
                cmd = ["unshare", "-n", "python3", str(test_script)]
            elif sandbox_tool == "firejail":
                cmd = ["firejail", "--noprofile", "--quiet", "python3", str(test_script)]
            elif sandbox_tool == "bwrap":
                cmd = [
                    "bwrap", "--die-with-parent", "--unshare-net",
                    "--ro-bind", "/usr", "/usr",
                    "--ro-bind", "/bin", "/bin",
                    "--tmpfs", "/tmp",
                    "--bind", str(tmpdir), "/work",
                    "--chdir", "/work",
                    "--", "python3", "/work/test_write.py"
                ]
            else:
                return {"executed": False, "reason": f"Unknown sandbox: {sandbox_tool}"}
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            output = result.stdout.strip()
            write_succeeded = (external_dir / 'test.txt').exists()
            return {
                "executed": True,
                "output": output,
                "write_blocked": not write_succeeded
            }
        except subprocess.TimeoutExpired:
            return {"executed": False, "reason": "Timeout"}
        except Exception as e:
            return {"executed": False, "reason": str(e)}
        finally:
            shutil.rmtree(external_dir, ignore_errors=True)
