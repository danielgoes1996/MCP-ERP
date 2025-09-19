#!/usr/bin/env python3
"""
Simple HTTP server for MCP Server without external dependencies
Use this if you can't install FastAPI dependencies
"""

import json
import http.server
import socketserver
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import uuid

from core.internal_db import initialize_internal_database

PORT = 8004

class MCPHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_json({"status": "MCP Server running"})
        elif self.path == '/health':
            self.send_json({"status": "healthy", "version": "1.0.0"})
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == '/mcp':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))

                method = data.get('method')
                params = data.get('params', {})

                result = self.handle_mcp_request(method, params)
                self.send_json({"success": True, "data": result})

            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, status=500)
        else:
            self.send_error(404)

    def handle_mcp_request(self, method, params):
        # Usar el handler real desde core/mcp_handler.py
        try:
            from core.mcp_handler import handle_mcp_request
            return handle_mcp_request(method, params)
        except ImportError:
            # Fallback a implementación simple si no se puede importar
            if method == "get_inventory":
                product_id = params.get("product_id", "UNKNOWN")
                return {
                    "product_id": product_id,
                    "quantity": 150,
                    "location": params.get("location", "WAREHOUSE_A"),
                    "last_updated": datetime.now().isoformat()
                }
            elif method == "create_order":
                return {
                    "order_id": str(uuid.uuid4())[:8].upper(),
                    "status": "confirmed",
                    "customer": params.get("customer", "DEFAULT_CUSTOMER"),
                    "created_date": datetime.now().isoformat()
                }
            elif method == "create_expense":
                return {
                    "expense_id": str(uuid.uuid4())[:8].upper(),
                    "status": "pending_approval",
                    "employee": params.get("employee", "DEFAULT_EMPLOYEE"),
                    "amount": params.get("amount", 0.0),
                    "date": datetime.now().isoformat()
                }
            else:
                raise Exception("Method not supported")

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

if __name__ == "__main__":
    try:
        initialize_internal_database()
        print("✅ Internal account catalog ready.")
    except Exception as exc:
        print(f"❌ Failed to initialise internal database: {exc}")
        raise

    with socketserver.TCPServer(("", PORT), MCPHandler) as httpd:
        print(f"🚀 MCP Server running at http://localhost:{PORT}")
        print(f"📖 Test endpoint: http://localhost:{PORT}/mcp")
        httpd.serve_forever()
