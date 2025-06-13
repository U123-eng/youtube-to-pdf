import streamlit as st
import os
import cv2
import tempfile
import re
from fpdf import FPDF
from PIL import Image
import yt_dlp
from skimage.metrics import structural_similarity as ssim
import whisper

# Load Whisper model
model = whisper.load_model("base")

# Extract video ID from URL
def get_video_id(url):
    patterns = [r"shorts\/([\w\-]+)", r"youtu\.be\/([\w\-]+)", r"v=([\w\-]+)", r"live\/([\w\-]+)"]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

# Download YouTube video
def download_video(url, filename="video.mp4"):
    ydl_opts = {
        'outtmpl': filename,
        'format': 'best',
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return filename
    except Exception as e:
        st.error(f"Download error: {e}")
        return None

# Extract frames using SSIM
def extract_unique_frames(video_file, output_folder, n=3, ssim_threshold=0.8):
    cap = cv2.VideoCapture(video_file)
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    last_frame, saved_frame = None, None
    frame_number, last_saved_frame_number = 0, -1
    timestamps = []

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        if frame_number % n == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, (128, 72))

            if last_frame is not None:
                similarity = ssim(gray, last_frame)
                if similarity < ssim_threshold and frame_number - last_saved_frame_number > fps:
                    save_path = os.path.join(output_folder, f"frame{frame_number}.png")
                    cv2.imwrite(save_path, saved_frame)
                    timestamps.append((frame_number, frame_number / fps))
                    last_saved_frame_number = frame_number
            else:
                save_path = os.path.join(output_folder, f"frame{frame_number}.png")
                cv2.imwrite(save_path, frame)
                timestamps.append((frame_number, frame_number / fps))
                last_saved_frame_number = frame_number

            last_frame = gray
            saved_frame = frame

        frame_number += 1

    cap.release()
    return timestamps

# Generate PDF with timestamps and subtitles
def convert_frames_to_pdf(input_folder, output_pdf, timestamps, subtitles):
    pdf = FPDF("L")
    pdf.set_auto_page_break(0)

    files = sorted(os.listdir(input_folder), key=lambda x: int(x.replace("frame", "").replace(".png", "")))
    for i, (filename, (_, seconds)) in enumerate(zip(files, timestamps)):
        img_path = os.path.join(input_folder, filename)
        pdf.add_page()
        pdf.image(img_path, x=0, y=0, w=pdf.w, h=pdf.h)
        time_str = f"{int(seconds//3600):02}:{int((seconds%3600)//60):02}:{int(seconds%60):02}"
        subtitle = subtitles.get(round(seconds), "")

        pdf.set_xy(10, 10)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", size=12)
        pdf.cell(0, 10, f"{time_str} - {subtitle}")

    pdf.output(output_pdf)

# Transcribe audio using Whisper
def transcribe_audio(file):
    result = model.transcribe(file)
    transcription = result['segments']
    subtitles = {}
    for segment in transcription:
        start_sec = int(segment['start'])
        text = segment['text'].strip()
        if start_sec not in subtitles:
            subtitles[start_sec] = text
    return subtitles

# Streamlit UI
st.title("🎥 YouTube Video to PDF Converter with Transcript")
st.markdown("Paste a YouTube video or Shorts link. It downloads the video, extracts key frames, transcribes audio, and generates a PDF with frames and spoken text.")

url = st.text_input("🔗 Enter YouTube Video URL:")

if st.button("Generate PDF"):
    if not url:
        st.warning("Please enter a YouTube link.")
    else:
        with st.spinner("Processing video, extracting frames, transcribing audio and generating PDF..."):
            video_id = get_video_id(url)
            if not video_id:
                st.error("Invalid YouTube URL format.")
            else:
                video_title = f"video_{video_id}"
                with tempfile.TemporaryDirectory() as tempdir:
                    video_path = os.path.join(tempdir, "video.mp4")
                    pdf_path = os.path.join(tempdir, f"{video_title}.pdf")

                    result = download_video(url, video_path)
                    if not result:
                        st.error("Video download failed.")
                    else:
                        subtitles = transcribe_audio(video_path)
                        timestamps = extract_unique_frames(video_path, tempdir)
                        convert_frames_to_pdf(tempdir, pdf_path, timestamps, subtitles)

                        with open(pdf_path, "rb") as f:
                            st.success("✅ PDF Generated Successfully!")
                            st.download_button(label="📄 Download PDF",
                                               data=f,
                                               file_name=f"{video_title}.pdf",
                                               mime="application/pdf")
