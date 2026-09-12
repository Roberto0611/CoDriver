import { useState, useRef } from 'react'

export default function ElevenLabsTest() {
  const [recording, setRecording] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [transcription, setTranscription] = useState('')
  const [reply, setReply] = useState('')
  const [errorMsg, setErrorMsg] = useState('')

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<BlobPart[]>([])
  const audioElementRef = useRef<HTMLAudioElement | null>(null)

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      mediaRecorderRef.current = mediaRecorder
      audioChunksRef.current = []

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          audioChunksRef.current.push(e.data)
        }
      }

      mediaRecorder.onstop = async () => {
        setProcessing(true)
        setErrorMsg('')
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' })
        const formData = new FormData()
        formData.append('file', audioBlob, 'grabacion.webm')

        try {
          // 1. Enviar audio al backend (STT + OpenRouter LLM)
          const response = await fetch('/api/voice/agent', {
            method: 'POST',
            body: formData,
          })

          if (!response.ok) {
            const err = await response.json()
            throw new Error(err.detail || 'Error en el servidor')
          }

          const data = await response.json()
          setTranscription(data.transcription)
          setReply(data.reply)

          // 2. Reproducir la respuesta automáticamente usando ElevenLabs TTS
          if (audioElementRef.current && data.reply) {
            const url = `/api/voice/say?text=${encodeURIComponent(data.reply)}`
            audioElementRef.current.src = url
            audioElementRef.current.play()
          }
        } catch (error: any) {
          setErrorMsg(error.message)
        } finally {
          setProcessing(false)
          // Detener todos los tracks del micrófono
          stream.getTracks().forEach((track) => track.stop())
        }
      }

      mediaRecorder.start()
      setRecording(true)
    } catch (err) {
      setErrorMsg('No se pudo acceder al micrófono. ' + err)
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && recording) {
      mediaRecorderRef.current.stop()
      setRecording(false)
    }
  }

  return (
    <div style={{ padding: '40px', fontFamily: 'sans-serif', maxWidth: '800px', margin: '0 auto' }}>
      <h1>🎤 Agente Multilingüe (Nuez)</h1>
      <p style={{ lineHeight: 1.6, color: '#444' }}>
        Habla en Español, Inglés o Hindi. El agente detectará tu idioma, pensará usando Gemini 2.5
        Flash Lite y responderá con su propia voz.
      </p>

      <div
        style={{
          marginTop: '30px',
          padding: '20px',
          border: '1px solid #ddd',
          borderRadius: '8px',
          background: '#f9f9f9',
          textAlign: 'center',
        }}
      >
        <button
          onClick={recording ? stopRecording : startRecording}
          disabled={processing}
          style={{
            padding: '16px 32px',
            background: recording ? '#dc2626' : processing ? '#9ca3af' : '#2563eb',
            color: 'white',
            border: 'none',
            borderRadius: '50px',
            cursor: processing ? 'not-allowed' : 'pointer',
            fontSize: '18px',
            fontWeight: 'bold',
            transition: 'background 0.2s',
            boxShadow: recording ? '0 0 15px rgba(220, 38, 38, 0.6)' : 'none',
          }}
        >
          {processing
            ? '🧠 Procesando...'
            : recording
              ? '🛑 Detener y Enviar'
              : '🎤 Presionar para Hablar'}
        </button>

        {errorMsg && (
          <div
            style={{
              marginTop: '20px',
              color: '#dc2626',
              background: '#fee2e2',
              padding: '10px',
              borderRadius: '4px',
            }}
          >
            {errorMsg}
          </div>
        )}

        <div
          style={{
            marginTop: '30px',
            textAlign: 'left',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px',
          }}
        >
          <div
            style={{
              background: '#eff6ff',
              padding: '15px',
              borderRadius: '8px',
              border: '1px solid #bfdbfe',
            }}
          >
            <strong>Tú dijiste:</strong>
            <p style={{ margin: '10px 0 0', fontSize: '16px', color: '#1e3a8a' }}>
              {transcription || '...'}
            </p>
          </div>

          <div
            style={{
              background: '#f0fdf4',
              padding: '15px',
              borderRadius: '8px',
              border: '1px solid #bbf7d0',
            }}
          >
            <strong>Nuez respondió:</strong>
            <p style={{ margin: '10px 0 0', fontSize: '16px', color: '#166534' }}>
              {reply || '...'}
            </p>
          </div>
        </div>

        <audio ref={audioElementRef} style={{ display: 'none' }} />
      </div>
    </div>
  )
}
