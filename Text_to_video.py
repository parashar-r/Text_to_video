import streamlit as st
import tempfile, os, numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips, vfx
from gtts import gTTS
from io import BytesIO

# ---------- Helper Functions ----------

def create_voiceover(text, lang='en'):
    """Generate voiceover audio using gTTS and return an AudioFileClip and the temp file path."""
    tts = gTTS(text=text, lang=lang)
    temp_fd, temp_path = tempfile.mkstemp(suffix=".mp3")
    os.close(temp_fd)
    tts.save(temp_path)
    audio_clip = AudioFileClip(temp_path)
    return audio_clip, temp_path

def create_slide_image(slide, resolution=(1920, 1080)):
    """
    Create a slide image as a NumPy array.
    
    - If a file is uploaded (for image slides), that image is used as the background.
    - Otherwise, a blank image is created with the selected background color.
    - Slide text is drawn at the specified (x,y) position with the given text size and color.
    """
    # Create background image either from file upload or from a plain background.
    if slide.get("uploaded_file") is not None:
        # uploaded_file is a BytesIO object.
        img = Image.open(slide["uploaded_file"]).convert("RGB")
        img = img.resize(resolution)
    else:
        # Use the background color (hex string, e.g., "#000000").
        img = Image.new("RGB", resolution, color=slide.get("bg_color", "#000000"))
    
    # If there is text to display, overlay it.
    text = slide.get("text", "")
    if text.strip() != "":
        draw = ImageDraw.Draw(img)
        try:
            # You can adjust the font file path if needed.
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", int(slide.get("text_size", 48)))
        except Exception:
            font = ImageFont.load_default()
        # Get text dimensions using textbbox.
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        # Get user-specified text position.
        pos_x, pos_y = slide.get("text_position", (resolution[0]//2, resolution[1]//2))
        # If position is center (-1, -1) then recalc to center.
        if pos_x == -1 or pos_y == -1:
            pos_x = (resolution[0] - text_width) // 2
            pos_y = (resolution[1] - text_height) // 2
        draw.text((pos_x, pos_y), text, fill=slide.get("text_color", "#FFFFFF"), font=font)
    return np.array(img)

def animate_clip(clip, fade_duration=1):
    """Apply fade-in and fade-out effects to a clip."""
    return clip.fx(vfx.fadein, fade_duration).fx(vfx.fadeout, fade_duration)

def create_video_from_slides(slides, resolution=(1920, 1080), output_file="output_video.mp4"):
    """
    For each slide dictionary, create an ImageClip with:
      - Customized background (or uploaded image)
      - Drawn text per user-specified font size, position, and color.
      - A voiceover audio generated from the slide’s voiceover text.
      - Duration set to max(user slide duration, voiceover duration).
      - Fade-in/out animations applied.
    Finally, concatenate all clips and write to a video file.
    Returns the path to the output video.
    """
    clips = []
    audio_temp_files = []

    for slide in slides:
        # Create voiceover.
        voice_text = slide.get("voiceover", slide.get("text", ""))
        voice_lang = slide.get("voice_lang", "en")
        voiceover, temp_audio_path = create_voiceover(voice_text, lang=voice_lang)
        audio_temp_files.append(temp_audio_path)
        
        # Determine slide duration.
        base_duration = float(slide.get("duration", 4))
        duration = max(base_duration, voiceover.duration)
        
        # Create the slide image.
        img_array = create_slide_image(slide, resolution=resolution)
        clip = ImageClip(img_array).set_duration(duration)
        fade_duration = float(slide.get("fade_duration", 1))
        clip = animate_clip(clip, fade_duration=fade_duration)
        clip = clip.set_audio(voiceover)
        clips.append(clip)
    
    # Concatenate all slide clips.
    final_clip = concatenate_videoclips(clips, method="compose")
    final_clip.write_videofile(output_file, fps=24)
    
    # Clean up temporary audio files.
    for temp_path in audio_temp_files:
        os.remove(temp_path)
    return output_file

# ---------- Streamlit App ----------

st.set_page_config(page_title="LEAPS Video Creator", layout="wide")
st.title("LEAPS 1080p Video Creator")

st.sidebar.header("Global Settings")
# For now, we fix the resolution to 1080p.
resolution = (1920, 1080)
output_format = st.sidebar.selectbox("Output Format", options=["mp4"], index=0)

st.sidebar.write("This tool creates 1080p videos.")

# Choose the number of slides.
num_slides = st.number_input("Number of Slides", min_value=1, max_value=20, value=3, step=1)

st.write("### Slide Customization")
slides_data = []

for i in range(int(num_slides)):
    st.markdown(f"#### Slide {i+1}")
    col1, col2 = st.columns(2)
    with col1:
        slide_type = st.selectbox("Slide Type", options=["title", "default", "image", "end"], key=f"slide_type_{i}")
        slide_text = st.text_area("Slide Text", key=f"slide_text_{i}", help="Enter the text to appear on the slide.")
        voiceover_text = st.text_area("Voiceover Text (optional)", key=f"voiceover_text_{i}", help="Defaults to slide text if left blank.")
        slide_duration = st.number_input("Slide Duration (seconds)", min_value=1.0, max_value=60.0, value=4.0, step=0.5, key=f"duration_{i}")
        fade_duration = st.number_input("Fade Duration (seconds)", min_value=0.0, max_value=5.0, value=1.0, step=0.1, key=f"fade_{i}")
        voice_lang = st.selectbox("Voiceover Language", options=["en", "es", "fr", "de"], index=0, key=f"voice_lang_{i}")
    with col2:
        text_size = st.number_input("Text Size (Font Size)", min_value=10, max_value=200, value=48, step=1, key=f"text_size_{i}")
        text_x = st.number_input("Text X Position (px, -1 for center)", min_value=-1, max_value=resolution[0], value=-1, step=1, key=f"text_x_{i}")
        text_y = st.number_input("Text Y Position (px, -1 for center)", min_value=-1, max_value=resolution[1], value=-1, step=1, key=f"text_y_{i}")
        bg_color = st.color_picker("Background Color", value="#000000", key=f"bg_color_{i}")
        text_color = st.color_picker("Text Color", value="#FFFFFF", key=f"text_color_{i}")
        if slide_type == "image":
            uploaded_file = st.file_uploader("Upload Background Image (optional)", type=["jpg", "jpeg", "png"], key=f"image_{i}")
        else:
            uploaded_file = None
    
    slide_data = {
        "type": slide_type,
        "text": slide_text,
        "voiceover": voiceover_text if voiceover_text.strip() != "" else slide_text,
        "text_size": text_size,
        "text_position": (text_x, text_y),
        "bg_color": bg_color,
        "text_color": text_color,
        "duration": slide_duration,
        "fade_duration": fade_duration,
        "voice_lang": voice_lang,
        "uploaded_file": uploaded_file
    }
    slides_data.append(slide_data)

if st.button("Generate Video"):
    with st.spinner("Generating video..."):
        video_file = tempfile.mktemp(suffix=".mp4")
        video_path = create_video_from_slides(slides_data, resolution=resolution, output_file=video_file)
    st.success("Video generated!")
    st.video(video_path)
    with open(video_path, "rb") as f:
        video_bytes = f.read()
    st.download_button("Download Video", data=video_bytes, file_name="leaps_video.mp4", mime="video/mp4")
