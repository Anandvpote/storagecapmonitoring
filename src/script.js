async function uploadFile() {
    const fileInput = document.getElementById('fileInput');
    const response = document.getElementById('response');
    const files = fileInput.files;

    // Clear previous response
    response.textContent = '';
    response.className = '';

    if (files.length === 0) {
        response.textContent = 'Please select at least one file to upload.';
        response.className = 'error';
        return;
    }

    try {
        response.textContent = 'Uploading...';
        response.className = '';
        response.style.display = 'block';

        const formData = new FormData();
        for (let i = 0; i < files.length; i++) {
            formData.append('files', files[i]);
        }

        const uploadResponse = await fetch('/api/blobuploader', {
            method: 'POST',
            body: formData
        });

        const result = await uploadResponse.json();

        if (uploadResponse.ok) {
            response.textContent = result.message;
            response.className = 'success';
        } else {
            throw new Error(result.error || 'Upload failed');
        }
    } catch (error) {
        response.textContent = `Error: ${error.message}`;
        response.className = 'error';
    }

    // Clear the file input
    fileInput.value = '';
}
