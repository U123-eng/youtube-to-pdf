import streamlit as st
from pytube import YouTube
import os
from moviepy.editor import VideoFileClip
from fpdf import FPDF
from PIL import Image
import tempfile
import shutil

st.set_page_config(page_title="YouTube Video to PDF", layout="centered")
st.title("📄 YouTube Video to PDF Converter")
st.write("Paste a YouTube video link and generate a PDF with frames and timestamps.")

url = st.text_input("Enter YouTube Video URL:")

if st.button("Generate PDF") and url:
    try:
        with st.spinner("Downloading video..."):
            yt = YouTube(url)
            video_stream = yt.streams.filter(file_extension='mp4', progressive=True).first()
            if not video_stream:
                st.error("No MP4 stream available.")
                st.stop()

            tempdir = tempfile.mkdtemp()
            video_path = os.path.join(tempdir, "video.mp4")
            video_stream.download(output_path=tempdir, filename="video.mp4")

        with st.spinner("Extracting frames..."):
            clip = VideoFileClip(video_path)
            duration = int(clip.duration)
            frame_folder = os.path.join(tempdir, "frames")
            os.makedirs(frame_folder, exist_ok=True)

            timestamps = []
            for t in range(0, duration, max(1, duration // 10)):  # 10 frames max
                frame_path = os.path.join(frame_folder, f"frame_{t}.png")
                clip.save_frame(frame_path, t)
                timestamps.append((frame_path, t))

        with st.spinner("Creating PDF..."):
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)

            for frame_path, t in timestamps:
                pdf.add_page()
                pdf.set_font("Arial", size=12)
                pdf.cell(200, 10, txt=f"Timestamp: {t} sec", ln=True)
                pdf.image(frame_path, x=10, y=30, w=pdf.w - 20)

            pdf_path = os.path.join(tempdir, "output.pdf")
            pdf.output(pdf_path)

        with open(pdf_path, "rb") as f:
            st.success("PDF generated successfully!")
            st.download_button("📥 Download PDF", f, file_name="video_summary.pdf")

    except Exception as e:
        st.error(f"Error: {e}")
    finally:
        if 'tempdir' in locals():
            shutil.rmtree(tempdir, ignore_errors=True)
