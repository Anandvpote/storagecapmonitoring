import logging
import azure.functions as func
import pandas as pd
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient
import os
import tempfile

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')
    
    # Set CORS headers
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type'
    }
    
    # Handle CORS preflight request
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=200, headers=headers)
    
    try:
        # Check if storage connection string is available
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        if not connection_string:
            return func.HttpResponse(
                '{"error": "Storage configuration error"}',
                status_code=500,
                headers=headers,
                mimetype="application/json"
            )

        # Get the files from the request
        files = req.files.to_dict()
        if not files or 'files' not in files:
            return func.HttpResponse(
                '{"error": "No file uploaded"}',
                status_code=400,
                headers=headers,
                mimetype="application/json"
            )

        file = files['files']
        filename = file.filename
        extension = os.path.splitext(filename)[1].lower()

        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
            file.save(tmp.name)
            temp_path = tmp.name

        # Process file based on type
        if extension == '.csv':
            df = pd.read_csv(temp_path)
        elif extension == '.xlsx':
            df = pd.read_excel(temp_path, engine='openpyxl')
        else:
            os.remove(temp_path)
            return func.HttpResponse(
                '{"error": "Unsupported file format"}',
                status_code=400,
                headers=headers,
                mimetype="application/json"
            )

        # Add Month and Year columns
        today = datetime.today()
        last_month_date = today - timedelta(days=today.day)
        df.insert(0, 'Month', last_month_date.strftime('%B'))
        df.insert(1, 'Year', today.year)

        # Save processed file
        new_filename = f"sa-capacity-report-{today.year}-{last_month_date.strftime('%b')}.xlsx"
        output_path = os.path.join(tempfile.gettempdir(), new_filename)
        df.to_excel(output_path, index=False, engine='openpyxl')

        # Upload to Azure Blob Storage
        container_name = "sa-capa-rep"
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        
        # Create container if it doesn't exist
        try:
            container_client = blob_service_client.get_container_client(container_name)
            container_client.create_container()
        except Exception as e:
            logging.info(f"Container {container_name} already exists")
        
        # Upload file
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=new_filename)
        with open(output_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)

        # Cleanup temporary files
        os.remove(temp_path)
        os.remove(output_path)

        return func.HttpResponse(
            '{"message": "File uploaded and processed successfully"}',
            status_code=200,
            headers=headers,
            mimetype="application/json"
        )

    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return func.HttpResponse(
            f'{{"error": "Internal server error: {str(e)}"}}',
            status_code=500,
            headers=headers,
            mimetype="application/json"
        )
