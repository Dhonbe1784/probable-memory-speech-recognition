document.addEventListener('DOMContentLoaded', function() {
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const statusText = document.getElementById('statusText');
    const transcriptionEl = document.getElementById('transcription');
    const pulseEl = document.querySelector('.pulse');
    
    let isRecording = false;
    let mediaRecorder;
    let audioStream;
    let transcriptionPolling;
    
    // Update button states
    function updateButtonStates() {
        startBtn.disabled = isRecording;
        stopBtn.disabled = !isRecording;
        pulseEl.style.display = isRecording ? 'block' : 'none';
    }
    
    // Update status message
    function updateStatus(message, isRecording = false) {
        statusText.textContent = message;
        statusText.className = isRecording ? 'recording-active' : '';
    }
    
    // Start recording
    startBtn.addEventListener('click', async () => {
        try {
            // Start new recording session on server
            const response = await fetch('/start_recording', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const data = await response.json();
            
            if (data.status !== 'success') {
                updateStatus(`Error: ${data.message}`, false);
                return;
            }
            
            // Reset UI
            transcriptionEl.textContent = 'Listening...';
            updateStatus("Recording... Speak now!", true);
            
            // Start transcription polling
            if (transcriptionPolling) clearInterval(transcriptionPolling);
            transcriptionPolling = setInterval(updateTranscription, 1000);
            
            // Get microphone access
            audioStream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true
                }
            });
            
            // Set up media recorder
            mediaRecorder = new MediaRecorder(audioStream, {
                mimeType: 'audio/webm;codecs=opus',
                audioBitsPerSecond: 16000
            });
            
            mediaRecorder.ondataavailable = async (event) => {
                if (event.data.size > 0) {
                    // Send to server
                    try {
                        await fetch('/audio_stream', {
                            method: 'POST',
                            body: await event.data.arrayBuffer(),
                            headers: {
                                'Content-Type': 'application/octet-stream'
                            }
                        });
                    } catch (error) {
                        console.error('Error sending audio chunk:', error);
                    }
                }
            };
            
            // Start recording in chunks
            mediaRecorder.start(500); // 500ms chunks
            isRecording = true;
            updateButtonStates();
            
        } catch (error) {
            updateStatus(`Error: ${error.message}`, false);
            console.error('Recording error:', error);
        }
    });
    
    // Stop recording
    stopBtn.addEventListener('click', async () => {
        try {
            if (mediaRecorder && isRecording) {
                mediaRecorder.stop();
                audioStream.getTracks().forEach(track => track.stop());
                
                if (transcriptionPolling) clearInterval(transcriptionPolling);
                
                // Stop recording on server
                const response = await fetch('/stop_recording', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                const data = await response.json();
                
                if (data.status === 'success') {
                    updateStatus("Recording completed", false);
                    transcriptionEl.textContent = data.transcription || "No speech detected";
                } else {
                    updateStatus(`Error: ${data.message}`, false);
                }
                
                isRecording = false;
                updateButtonStates();
            }
        } catch (error) {
            updateStatus(`Error: ${error.message}`, false);
            console.error('Stop recording error:', error);
        }
    });
    
    // Update transcription display
    async function updateTranscription() {
        try {
            const response = await fetch('/get_transcription');
            const data = await response.json();
            
            if (data.transcription) {
                transcriptionEl.textContent = data.transcription;
                
                // Auto-scroll to bottom
                transcriptionEl.scrollTop = transcriptionEl.scrollHeight;
            }
        } catch (error) {
            console.error('Error fetching transcription:', error);
        }
    }
    
    // Initialize button states
    updateButtonStates();
    
    // Clean up on page unload
    window.addEventListener('beforeunload', () => {
        if (isRecording) {
            // Try to stop recording if page is closed
            stopBtn.click();
        }
    });
});
