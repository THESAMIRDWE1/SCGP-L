"""Sandboxed process execution with raw observation recording.

Executes target and candidate independently.
Records Layer 1 raw observations only.
No interpretation or classification at this level.
"""

import subprocess
import tempfile
import os
import signal
import time
from pathlib import Path
from typing import Optional, Tuple
from .types import RawObservation, ExecutionStatus


class ProcessExecutor:
    """Execute processes and record raw observations."""
    
    DEFAULT_TIMEOUT_SECONDS = 2.0
    MAX_OUTPUT_BYTES = 65536
    
    def __init__(self, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS):
        self.timeout_seconds = timeout_seconds
    
    def execute(self, cmd: list, input_data: str, cwd: Optional[Path] = None) -> RawObservation:
        """Execute command and return raw observation.
        
        Returns: RawObservation (Layer 1)
        """
        if cwd is None:
            cwd = Path.cwd()
        
        obs = RawObservation()
        obs.input_value = input_data
        
        # Use temporary files to avoid memory DoS
        stdout_file = tempfile.NamedTemporaryFile(delete=False, mode='w+b')
        stderr_file = tempfile.NamedTemporaryFile(delete=False, mode='w+b')
        stdout_path = stdout_file.name
        stderr_path = stderr_file.name
        stdout_file.close()
        stderr_file.close()
        
        try:
            wall_start = time.time()
            
            with open(stdout_path, 'w+b') as out, open(stderr_path, 'w+b') as err:
                try:
                    proc = subprocess.Popen(
                        cmd,
                        stdin=subprocess.PIPE,
                        stdout=out,
                        stderr=err,
                        cwd=str(cwd),
                        text=True,
                        start_new_session=True  # Create process group for cleanup
                    )
                    
                    try:
                        proc.communicate(input=input_data + "\n", timeout=self.timeout_seconds)
                        obs.exit_code_candidate = proc.returncode
                        obs.timed_out = False
                    except subprocess.TimeoutExpired:
                        obs.timed_out = True
                        obs.exit_code_candidate = -999
                        try:
                            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        proc.wait()
                except Exception as e:
                    obs.crashed = True
                    obs.stderr_candidate = repr(e)
                    obs.exit_code_candidate = -998
            
            wall_end = time.time()
            obs.wall_time_candidate_ms = (wall_end - wall_start) * 1000
            
            # Read bounded output
            with open(stdout_path, 'rb') as f:
                stdout_data = f.read(self.MAX_OUTPUT_BYTES + 1)
            with open(stderr_path, 'rb') as f:
                stderr_data = f.read(self.MAX_OUTPUT_BYTES + 1)
            
            obs.candidate_output = stdout_data[:self.MAX_OUTPUT_BYTES].decode('utf-8', errors='replace')
            obs.stderr_candidate = stderr_data[:self.MAX_OUTPUT_BYTES].decode('utf-8', errors='replace')
            
        finally:
            for p in [stdout_path, stderr_path]:
                try:
                    os.unlink(p)
                except FileNotFoundError:
                    pass
        
        return obs
    
    def execute_target_and_candidate(
        self,
        target_cmd: list,
        candidate_cmd: list,
        input_data: str,
        target_cwd: Optional[Path] = None,
        candidate_cwd: Optional[Path] = None
    ) -> RawObservation:
        """Execute both target and candidate, return combined observation.
        
        Returns: RawObservation with both results (Layer 1)
        """
        obs_target = self.execute(target_cmd, input_data, target_cwd)
        obs_candidate = self.execute(candidate_cmd, input_data, candidate_cwd)
        
        # Merge observations
        merged = RawObservation(
            input_value=input_data,
            target_output=obs_target.candidate_output,
            candidate_output=obs_candidate.candidate_output,
            exit_code_target=obs_target.exit_code_candidate,
            exit_code_candidate=obs_candidate.exit_code_candidate,
            wall_time_target_ms=obs_target.wall_time_candidate_ms,
            wall_time_candidate_ms=obs_candidate.wall_time_candidate_ms,
            stderr_target=obs_target.stderr_candidate,
            stderr_candidate=obs_candidate.stderr_candidate,
            timed_out=obs_target.timed_out or obs_candidate.timed_out,
            crashed=obs_target.crashed or obs_candidate.crashed,
        )
        
        # Compute matches
        merged.output_bytes_match = (
            merged.target_output.encode() == merged.candidate_output.encode()
        )
        merged.exit_code_match = (
            merged.exit_code_target == merged.exit_code_candidate
        )
        
        return merged
