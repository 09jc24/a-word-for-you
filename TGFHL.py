import urllib.parse
import time
import requests
import streamlit as st
from google import genai
from openai import OpenAI

# 1. Configure the page
st.set_page_config(page_title="A Word For You", page_icon="logo.png", layout="centered")

st.markdown(""
    "<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;}</style",
    unsafe_allow_html=True,
    )

# 2. Initialize the Gemini AI client using Streamlit's secure Secrets
if "GEMINI_API_KEY" not in st.secrets:
    st.error("Please add your GEMINI_API_KEY in Streamlit App Settings -> Secrets.")
    st.stop()

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

# 3. Configuration dictionaries for translations and book filters
TRANSLATIONS = {
    "World English Bible (WEB)": {"api": "web", "bg": "WEB", "lang" : "English"},
    "King James Version (KJV)": {"api": "kjv", "bg": "KJV", "lang" : "English"},
    "American Standard Version (ASV)": {"api": "asv", "bg": "ASV", "lang" : "English"},
    "Reina Valera 1909 (Español)": {"api": "rv1909", "bg": "RVA", "lang" : "Spanish"},
    "Biblia en Español Sencillo (Español)": {"api": "bes", "bg": "PDT", "lang" : "Spanish"}
}

SCRIPTURE_FOCUS = {
    "English": {
        "Psalms & Proverbs (Wisdom & Comfort)": "PSA,PRO",
        "The Gospels (Life of Jesus)": "MAT,MRK,LUK,JHN",
        "New Testament": "NT",
        "Old Testament": "OT",
        "Whole Bible": "",
    },
    "Spanish": {
        "Salmos y Proverbios (Sabiduría y Consuelo)": "PSA,PRO",
        "Los Evangelios (Vida de Jesús)": "MAT,MRK,LUK,JHN",
        "Nuevo Testamento": "NT",
        "Antiguo Testamento": "OT",
        "Toda la Biblia": "",
    },
}

UI_TEXT = {
    "English": {
        "title": "🕊️ A Living Word For You",
        "subtitle": "Pause for a moment. Choose your translation, share what is on your heart, and receive a scripture with a personal meditation.",
        "trans_label": "Bible Translation",
        "focus_label": "Scripture Focus",
        "heart_label": "What is on your heart today? (Optional)",
        "heart_placeholder": "e.g., Feeling anxious about work, grateful for family, seeking direction...",
        "receive_btn": "✨ Receive My Message",
        "receive_spinner": "Seeking a word for you...",
        "bg_btn": "📖 Read Surrounding Chapter on Bible Gateway",
        "deeper_header": "🕊️ Go Deeper",
        "followup_label": "Want to reflect further on this verse? Add a specific prayer request or question (Optional):",
        "followup_placeholder": "e.g., How do I trust God with this at my job?",
        "deeper_btn": "🙏 Pray Deeper",
        "deeper_spinner": "Reflecting deeper...",
    },
    "Spanish": {
        "title": "🕊️ La Palabra Viva Para Ti",
        "subtitle": "Haz una pausa por un momento. Elige tu traducción, comparte lo que hay en tu corazón y recibe una escritura con una meditación personalizada.",
        "trans_label": "Versión de la Biblia",
        "focus_label": "Enfoque Bíblico",
        "heart_label": "¿Qué hay en tu corazón hoy? (Opcional)",
        "heart_placeholder": "ej., Ansioso(a) por el trabajo, agradecido(a) por mi familia, buscando dirección...",
        "receive_btn": "✨ Recibir Mi Mensaje",
        "receive_spinner": "Buscando por y para ti...",
        "bg_btn": "📖 Leer el Capítulo Completo en Bible Gateway",
        "deeper_header": "🕊️ Profundizar en Oración",
        "followup_label": "¿Quieres reflexionar más sobre este versículo? Añade una petición o pregunta (Opcional):",
        "followup_placeholder": "ej., ¿Cómo confío en Dios con esto en mi trabajo?",
        "deeper_btn": "🙏 Orar Más Profundo",
        "deeper_spinner": "Reflexionando más profundamente...",
    },
}

# 4. Function to fetch a random Bible verse for free
def get_random_verse(translation_key, focus_key):
    trans_info = TRANSLATIONS[translation_key]
    api_trans = trans_info["api"]
    bg_version = trans_info["bg"]
    lang = trans_info["lang"]
    books_ids = SCRIPTURE_FOCUS[lang][focus_key]

    # 4a. Build the parameterized random endpoint
    url = f"https://bible-api.com/data/{api_trans}/random"
    if books_ids:
        url += f"/{books_ids}"

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            verse_info = data.get("random_verse", {})
            book = verse_info.get("book", "Psalm")
            chapter = verse_info.get("chapter", 23)
            verse = verse_info.get("verse", 1)
            text = verse_info.get("text", "").strip()

            reference = f"{book} {chapter}:{verse}"
            encoded_ref = urllib.parse.quote(reference)
            link = f"https://biblegateway.com/passage/?search={encoded_ref}&version={bg_version}"
            return reference, text, link
    except Exception:
        pass

    # Fallback verse if the external API briefly hiccups
    return (
        "Psalm 46:10",
        "Be still, and know that I am God.",
        f"https://biblegateway.com/passage/?search=Psalm%2046%3A10&version={bg_version}",
    )

# 5. Making the app resilient so visitors never see a raw Python traceback during high-demand spikes
def call_ai_with_fallback(prompt):
    # 5a. Automaticbackup using free Groq API if Gemini spikes
    if "GROQ_API_KEY" in st.secrets:
        try:
            groq_client = OpenAI(
                api_key=st.secrets["GROQ_API_KEY"],
                base_url="https://api.groq.com/openai/v1",
                timeout=8.0,  # Don't hnag if there's a network hiccup
            )
            chat = groq_client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[{"role": "user", "content": prompt}],
            )
            return chat.choices[0].message.content
        except Exception:
            pass

    # 5b. Try primary model first, then lighter fallback models if traffic spikes
    try:
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
        )
        return response.text
    except Exception:
        pass
    
    return None

# 6. Function to generate a personal AI meditation & prayer
def generate_reflection(reference, verse_text, user_heart, language="English"):
    heart_context = (
        f"The person reading this shared what is on their heart today: '{user_heart}'."
        if user_heart.strip()
        else "The person reading this is simply opening their heart to hear from God today."
    )

    meditation_header = "### 🌿 Una Meditación Personal" if language == "Spanish" else "### 🌿 A Personal Meditation"
    prayer_header = "### 🙏 Una Oración" if language == "Spanish" else "### 🙏 A Prayer to Pray"

    prompt = f"""
    You are a gentle, compassionate spiritual companion helping someone connect with God through Scripture.
    Respond completely in {language}.
    
    Scripture: "{verse_text}" ({reference})
    Context: {heart_context}

    Write a deeply personal, comforting response divided into two clear sections using Markdown headers:
    {meditation_header}
    Write 1 short, warm paragraph (3-4 sentences) speaking directly to the reader ("you") as if God is meeting them right where they are today through this specific verse. Avoid clichés and keep the tone intimate, peaceful, and encouraging.

    {prayer_header}
    Write a short, heartfelt first-person prayer ("Lord...", "Father...") that the user can pray aloud right now in response to this scripture.
    """
    result = call_ai_with_fallback(prompt)
    if result:
        return result

    # 6a. Graceful message if all models are momentarily busy
    return (
        "### 🌿 Momento de Quietud\nEl servicio de meditación está muy ocupado en este momento. Por favor, lee el versículo arriba y vuelve a intentarlo en unos segundos."
        if language == "Spanish"
        else "### 🌿 A Moment of Stillness\nThe reflection service is experiencing heavy traffic right now. Please pause with the scripture above and try again in a few seconds."
    )

# 7. Function to generate a deeper personal AI prayer
def generate_deeper_prayer(reference, verse_text, previous_reflection, followup_note, language="English"):

    deeper_header = "### 🕯️ Reflexión Profunda y Pregunta para Meditar" if language == "Spanish" else "### 🕯️ Deeper Reflection & Journaling Prompt"
    blessing_header = "### 🤍 Bendición Final" if language == "Spanish" else "### 🤍 Closing Blessing"

    prompt = f"""
    You are a gentle, compassionate spiritual companion continuing a devoltional moment.
    Respond completely in {language}.

    Scripture: "{verse_text}" ({reference})
    Previous Meditation & Prayer:
    {previous_reflection}

    The reader wants to go deeper. Their follow-up thought or focus is: '{followup_note if followup_note.strip() else "Help me apply this deeply to my life today."}'

    Provide two brief, thoughtful sections using Markdown headers:
    {deeper_header}
    Write 2-3 sentences exploring a deeper spiritual truth in this verse, followed by 1 reflective question for them to ponder or journal about.

    {blessing_header}
    Write a brief, 2-sentence pastoral blessing over the reader.
    """

    result = call_ai_with_fallback(prompt)
    if result:
        return result

    # 7a. Graceful message if all models are momentarily busy
    return (
        "### 🌿 Momento de Quietud\nEl servicio de meditación está muy ocupado en este momento. Por favor, lee el versículo arriba y vuelve a intentarlo en unos segundos."
        if language == "Spanish"
        else "### 🌿 A Moment of Stillness\nThe reflection service is experiencing heavy traffic right now. Please pause with the scripture above and try again in a few seconds."
    )

# 8. Build the User Interface
_, logo_col, _ = st.columns([2, 1, 2])
with logo_col:
    st.image("logo.png", width="stretch")

col1, col2 = st.columns(2)
with col1:
    selected_translation = st.selectbox("Bible Translation / Traducción", list(TRANSLATIONS.keys()))

# 8a. Detect actie language immediately from the selected translation
current_lang = TRANSLATIONS[selected_translation]["lang"]
ui = UI_TEXT[current_lang]

with col2:
    selected_focus = st.selectbox(ui["focus_label"], list(SCRIPTURE_FOCUS[current_lang].keys()))

st.title(ui["title"])
st.write(ui["subtitle"])

user_heart = st.text_input(
    ui["heart_label"],
    placeholder=ui["heart_placeholder"]
)

if st.button(ui["receive_btn"], type="primary"):
    with st.spinner(ui["receive_spinner"]):
        lang = TRANSLATIONS[selected_translation]["lang"]
        ref, text, link = get_random_verse(selected_translation, selected_focus)
        reflection = generate_reflection(ref, text, user_heart, lang)
        st.session_state.message_data = {
            "ref": ref,
            "text": text,
            "link": link,
            "reflection": reflection,
            "lang": current_lang,
        }
        # 6a. Reset any previous "Pray Deeper" response when feching a new verse
        st.session_state.pop("deeper_data", None)

# 9. Display the personalized message
if "message_data" in st.session_state:
    data = st.session_state.message_data

    # 9a. Match display UI to the language of the generated message
    msg_ui = UI_TEXT[data["lang"]]

    st.divider()
    st.subheader(f'"{data["text"]}"')
    st.caption(f"— **{data['ref']}**")
    
    st.markdown(data["reflection"])
    
    st.divider()
    st.link_button(msg_ui["bg_btn"], data["link"])

    # 8b. "Pray Deeper" Follow-Up Section
    st.subheader(msg_ui["deeper_header"])
    followup_input = st.text_input(
        msg_ui["followup_label"],
        key="followup_box",
        placeholder=msg_ui["followup_placeholder"]
    )

    if st.button(msg_ui["deeper_btn"]):
        with st.spinner(msg_ui["deeper_spinner"]):
            deeper_text = generate_deeper_prayer(
                data["ref"],
                data["text"],
                data["reflection"],
                followup_input,
                data["lang"]
            )
            st.session_state.deeper_data = deeper_text

    if "deeper_data" in st.session_state:
        st.markdown(st.session_state.deeper_data)