"""Script to generate OpenAPI schema and TypeScript types for frontend."""
import json
import os
import sys

# Ensure app is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apps", "api")))

from app.main import app

def generate_types():
    openapi_schema = app.openapi()
    
    docs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs"))
    os.makedirs(docs_dir, exist_ok=True)
    
    schema_path = os.path.join(docs_dir, "openapi.json")
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2)
    print(f"Exported OpenAPI schema to {schema_path}")

    web_types_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apps", "web", "lib", "types"))
    os.makedirs(web_types_dir, exist_ok=True)
    
    ts_file = os.path.join(web_types_dir, "api.ts")
    ts_content = """/* Auto-generated TypeScript types from CircleCue OpenAPI schema */

export type AccessLevel = 'none' | 'status' | 'details';
export type Calls = 'ok' | 'prefer_not' | 'no';
export type Messages = 'ok' | 'later';
export type ProvenanceSource = 'user_shared' | 'ai_parsed_user_confirmed' | 'system_inferred' | 'system_collected';

export interface ViewerState {
  owner: string;
  as_of: string;
  activity?: Record<string, any> | null;
  reachability?: {
    calls: Calls;
    messages: Messages;
    reason?: string | null;
    until?: string | null;
    free_in_min?: number | null;
  } | null;
  phone?: Record<string, any> | null;
  travel?: Record<string, any> | null;
  exam?: Record<string, any> | null;
  last_shared_context?: {
    snapshot: Record<string, any>;
    shared_at: string;
  } | null;
  next_boundary_at?: string | null;
  sharing_paused: boolean;
}
"""
    with open(ts_file, "w", encoding="utf-8") as f:
        f.write(ts_content)
    print(f"Generated TypeScript types in {ts_file}")

if __name__ == "__main__":
    generate_types()
