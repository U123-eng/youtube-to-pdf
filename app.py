import os
import streamlit as st
import tempfile
import shutil
from fpdf import FPDF
import cv2
import numpy as np
import whisper
from PIL import Image
from yt_dlp import YoutubeDL

st.title("🎬 YouTube Video to PDF Converter")

def download_audio(video_url, output_path):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(output_path, 'audio.%(ext)s'),
        'quiet': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
        }],
    }
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])
    return os.path.join(output_path, 'audio.mp3')

def download_video(video_url, output_path):
    ydl_opts = {
        'format': 'mp4',
        'outtmpl': os.path.join(output_path, 'video.%(ext)s'),
        'quiet': True
    }
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])
    return os.path.join(output_path, 'video.mp4')

def extract_keyframes(video_path, output_folder, interval=5):
    cap = cv2.VideoCapture(video_path)
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    saved_frames = []

    for i in range(0, frame_count, interval * fps):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if not ret:
            break
        frame_path = os.path.join(output_folder, f"frame_{i}.png")
        cv2.imwrite(frame_path, frame)
        saved_frames.append((i // fps, frame_path))
    cap.release()
    return saved_frames

def transcribe_audio(audio_path):
    model = whisper.load_model("base")
    result = model.transcribe(audio_path)
    return result['segments']

def convert_to_pdf(frames, transcript, output_pdf):
    pdf = FPDF()
    for time_sec, frame_path in frames:
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=f"Timestamp: {time_sec}s", ln=True)
        img = Image.open(frame_path)
        img = img.convert('RGB')
        temp_img_path = frame_path.replace(".png", "_resized.jpg")
        img.save(temp_img_path)

        pdf.image(temp_img_path, x=10, y=20, w=180)

        matching_texts = [seg['text'] for seg in transcript if int(seg['start']) <= time_sec <= int(seg['end'])]
        text_block = "\n".join(matching_texts) if matching_texts else "No matching text found."

        pdf.ln(85)
        pdf.multi_cell(0, 10, text_block)
    pdf.output(output_pdf)

st.write("Paste a YouTube video URL below to generate a PDF of frames + transcript.")

video_url = st.text_input("Enter YouTube Video URL:")

if st.button("Generate PDF"):
    if video_url.strip() == "":
        st.warning("Please enter a valid YouTube URL.")
    else:
        with st.spinner("Processing..."):
            tempdir = tempfile.mkdtemp()
            try:
                audio_path = download_audio(video_url, tempdir)
                video_path = download_video(video_url, tempdir)
                transcript = transcribe_audio(audio_path)
                frames = extract_keyframes(video_path, tempdir, interval=5)
                output_pdf_path = os.path.join(tempdir, "output.pdf")
                convert_to_pdf(frames, transcript, output_pdf_path)

                with open(output_pdf_path, "rb") as f:
                    st.success("PDF Generated Successfully!")
                    st.download_button("Download PDF", f, file_name="youtube_summary.pdf")
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                shutil.rmtree(tempdir)
