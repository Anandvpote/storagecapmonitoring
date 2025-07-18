# function_app_blob_upload/__init__.py

import logging
import azure.functions as func
import pandas as pd
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient
from openpyxl import load_workbook
from openpyxl.utils.dataframe import dataframe_to_rows
import os
import tempfile
import mimetypes

def serve_static_file(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # Get the path from the route
        path = req.route_params.get('restOfPath', '')
        
        # If no path or root path, serve index.html
        if not path or path == '/':
            path = 'index.html'
        
        # Remove leading slash if present
        path = path.lstrip('/')
        
        # Get the file path
        current_dir = os.path.dirname(os.path.realpath(__file__))
        file_path = os.path.join(current_dir, 'static', path)
        
        # Check if file exists
        if not os.path.exists(file_path):
            return func.HttpResponse(
                "File not found",
                status_code=404
            )
        
        # Get the mime type
        content_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
        
        # Read the file
        with open(file_path, 'rb') as f:
            content = f.read()
        
        return func.HttpResponse(
            content,
            mimetype=content_type,
            status_code=200
        )
    except Exception as e:
        logging.error(f"Error serving static file: {str(e)}")
        return func.HttpResponse(
            "Internal Server Error",
            status_code=500
        )

def handle_upload(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("📥 Received file upload request")
    
    # Set CORS headers for all responses
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type'
    }
    
    # Handle OPTIONS request
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=200, headers=headers)
    
    # Check if storage connection string is available
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        logging.error("Storage connection string not found")
        return func.HttpResponse(
            "Storage configuration error",
            status_code=500,
            headers=headers
        )

    try:
        # Get the file from the request
        files = req.files.to_dict()
        if not files or 'file' not in files:
            return func.HttpResponse(
                "❌ No file uploaded.", 
                status_code=400,
                headers=headers
            )
            
        file = files['file']

        filename = file.filename
        extension = os.path.splitext(filename)[1].lower()

        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
            file.save(tmp.name)
            temp_path = tmp.name
        # Read file
        if extension == '.csv':
            df = pd.read_csv(temp_path)
        elif extension == '.xlsx':
            df = pd.read_excel(temp_path, engine='openpyxl')
        else:
            response = func.HttpResponse("❌ Unsupported file format.", status_code=400)
            response.headers['Access-Control-Allow-Origin'] = 'http://localhost:8080'
            return response

        # Add Month and Year
        today = datetime.today()
        last_month_date = today - timedelta(days=today.day)
        df.insert(0, 'Month', last_month_date.strftime('%B'))
        df.insert(1, 'Year', today.year)

        # Save modified file
        new_filename = f"sa-capacity-report-{today.year}-{last_month_date.strftime('%b')}.xlsx"
        output_path = os.path.join(tempfile.gettempdir(), new_filename)
        df.to_excel(output_path, index=False, engine='openpyxl')

        # Upload to Azure Blob
        try:
            container_name = "sa-capa-rep"
            blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            
            # Create container if it doesn't exist
            try:
                container_client = blob_service_client.get_container_client(container_name)
                container_client.create_container()
                logging.info(f"Created container: {container_name}")
            except Exception as e:
                logging.info(f"Container {container_name} already exists or error: {str(e)}")
            
            blob_client = blob_service_client.get_blob_client(container=container_name, blob=new_filename)
            
            with open(output_path, "rb") as data:
                logging.info(f"Uploading blob: {new_filename}")
                blob_client.upload_blob(data, overwrite=True)
                logging.info("Upload completed successfully")
        except Exception as e:
            logging.error(f"Error uploading to blob storage: {str(e)}")
            raise

        # Cleanup
        os.remove(temp_path)
        os.remove(output_path)

        response = func.HttpResponse(f"✅ File uploaded as {new_filename}", status_code=200)
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:8080'
        return response

    except Exception as e:
        logging.error(f"❌ Error: {str(e)}")
        response = func.HttpResponse(f"❌ Internal Server Error: {str(e)}", status_code=500)
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:8080'
        return response
