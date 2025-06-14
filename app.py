import streamlit as st
import os
import cv2
import tempfile
import re
from fpdf import FPDF
from PIL import Image
import yt_dlp
from skimage.metrics import structural_similarity as ssim

# --- Extract video ID ---
def get_video_id(url):
    patterns = [r"shorts\/([\w\-]+)", r"youtu\.be\/([\w\-]+)", r"v=([\w\-]+)", r"live\/([\w\-]+)"]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

# --- Download video from YouTube without ffmpeg (safe for Streamlit Cloud) ---
def download_video(url, filename="video.mp4"):
    ydl_opts = {
        'outtmpl': filename,
        'format': 'best[ext=mp4]/mp4',  # Avoids merging, no ffmpeg needed
        'noplaylist': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return filename
    except Exception as e:
        st.error(f"Download error: {e}")
        return None

# --- Extract Unique Frames using SSIM ---
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
                    timestamps.append((frame_number, frame_number // fps))
                    last_saved_frame_number = frame_number
            else:
                save_path = os.path.join(output_folder, f"frame{frame_number}.png")
                cv2.imwrite(save_path, frame)
                timestamps.append((frame_number, frame_number // fps))
                last_saved_frame_number = frame_number

            last_frame = gray
            saved_frame = frame

        frame_number += 1

    cap.release()
    return timestamps

# --- Convert frames to PDF ---
def convert_frames_to_pdf(input_folder, output_pdf, timestamps):
    pdf = FPDF("L")
    pdf.set_auto_page_break(0)

    files = sorted(os.listdir(input_folder), key=lambda x: int(x.replace("frame", "").replace(".png", "")))
    for i, (filename, (_, seconds)) in enumerate(zip(files, timestamps)):
        img_path = os.path.join(input_folder, filename)
        img = Image.open(img_path)
        pdf.add_page()
        pdf.image(img_path, x=0, y=0, w=pdf.w, h=pdf.h)
        time_str = f"{seconds//3600:02}:{(seconds%3600)//60:02}:{seconds%60:02}"
        pdf.set_xy(10, 10)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", size=12)
        pdf.cell(0, 10, time_str)

    pdf.output(output_pdf)

# --- Streamlit UI ---
st.set_page_config(page_title="YouTube to PDF", layout="wide")
st.title("🎥 YouTube Video to PDF Generator")
st.markdown("🔗 Paste a YouTube video or Shorts link below. This tool will download the video, extract key frames, and generate a PDF summary with timestamps.")

url = st.text_input("Enter YouTube Video URL:")

if st.button("Generate PDF"):
    if not url:
        st.warning("Please enter a YouTube link.")
    else:
        with st.spinner("Processing video, extracting frames and generating PDF..."):
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
                        timestamps = extract_unique_frames(video_path, tempdir)
                        convert_frames_to_pdf(tempdir, pdf_path, timestamps)

                        with open(pdf_path, "rb") as f:
                            st.success("✅ PDF Generated Successfully!")
                            st.download_button(label="📄 Download PDF",
                                               data=f,
                                               file_name=f"{video_title}.pdf",
                                               mime="application/pdf")
