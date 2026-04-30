import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io
import json
from fpdf import FPDF
import openai

# ------------------------------
# App Configuration & Session State
# ------------------------------
st.set_page_config(
    page_title="Political Quadrant Strategy Tool",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

if "tasks" not in st.session_state:
    st.session_state.tasks = []
if "saved_campaigns" not in st.session_state:
    st.session_state.saved_campaigns = []
if "openai_api_key" not in st.session_state:
    st.session_state.openai_api_key = ""
if "demo_campaign" not in st.session_state:
    st.session_state.demo_campaign = None
if "latest_quadrant" not in st.session_state:
    st.session_state.latest_quadrant = None
if "custom_thresholds" not in st.session_state:
    st.session_state.custom_thresholds = {
        "high_pv": 70, "low_pv": 30,
        "high_vr": 70, "low_vr": 30,
        "high_pi": 70, "low_pi": 30,
        "high_momentum": 70
    }
if "score_history" not in st.session_state:
    st.session_state.score_history = {}

# ------------------------------
# Questionnaire Definitions
# ------------------------------
MATRIX_QUESTIONS = {
    "Voter Resonance (VR) - *Emotional Connection*": [
        "Do voters feel a personal connection to your story or background?",
        "Does your messaging evoke strong emotions (hope, outrage, pride) rather than just facts?",
        "Do supporters organically volunteer or spread your message without being prompted?"
    ],
    "Policy Viability (PV) - *Perceived Value*": [
        "Do voters explicitly state that your platform is 'realistic' and 'makes sense'?",
        "Does your platform offer clear solutions to problems that competitors ignore?",
        "Is your platform viewed as a serious governance plan rather than just empty promises?"
    ],
    "Public Integrity (PI) - *Trust*": [
        "Does your campaign have visible validation (key endorsements, press credibility)?",
        "Do voters feel confident you will keep your promises once elected?",
        "Is your brand considered 'clean' and free from major scandal or corruption perception?"
    ],
    "Campaign Momentum (M) - *Strategy Lever*": [
        "Is the race framed as 'tight' or 'critical' (driving urgency)?",
        "Does supporting you make voters feel like they are on the winning side?",
        "Are you setting the news cycle agenda, rather than reacting to it?"
    ]
}

# ------------------------------
# Core Political Matrix Logic (3-AXIS BINARY MAPPING)
# ------------------------------
class NormalizedScores:
    def __init__(self, voter_resonance: float, policy_viability: float, public_integrity: float, momentum: float):
        self.voter_resonance = round(voter_resonance, 2)
        self.policy_viability = round(policy_viability, 2)
        self.public_integrity = round(public_integrity, 2)
        self.momentum = round(momentum, 2)

def classify_quadrant(scores: NormalizedScores, custom_thresholds: dict = None) -> tuple[str, dict]:
    DEFAULT_THRESHOLDS = {
        "high_pv": 70, "low_pv": 30,
        "high_vr": 70, "low_vr": 30,
        "high_pi": 70, "low_pi": 30,
        "high_momentum": 70
    }
    thresholds = custom_thresholds or DEFAULT_THRESHOLDS
    vr, pv, pi = scores.voter_resonance, scores.policy_viability, scores.public_integrity

    b_vr = 1 if vr >= thresholds["high_vr"] else 0
    b_pv = 1 if pv >= thresholds["high_pv"] else 0
    b_pi = 1 if pi  >= thresholds["high_pi"] else 0

    key = f"{b_vr}{b_pv}{b_pi}" # Mapping logic: VR, PV, PI

    # POLITICAL QUADRANT MAP
    quadrant_map = {
        "000": "Q7: The Ghost Candidate",           # Low VR, Low PV, Low PI
        "001": "Q3: The Honest Outsider",           # Low VR, Low PV, High PI
        "010": "Q1: The Policy Wonk",               # Low VR, High PV, Low PI
        "011": "Q8: The Reliable Steward",          # Low VR, High PV, High PI
        "100": "Q6: The Agitator",                  # High VR, Low PV, Low PI
        "101": "Q4: The Beloved Figure",            # High VR, Low PV, High PI
        "110": "Q2: The Partisan Champion",         # High VR, High PV, Low PI
        "111": "Q5: The Unstoppable Force"          # High VR, High PV, High PI
    }

    quadrant_name = quadrant_map.get(key, "Unclassified Quadrant")
    return quadrant_name, thresholds

# ------------------------------
# Voter Targeting Profiles
# ------------------------------
def get_voter_targeting_strategy(quadrant: str) -> dict:
    targeting_profiles = {
        "Q1: The Policy Wonk": {
            "persona_name": "The Issue-Driven Voter",
            "core_psychology": "Votes based on white papers, debate performance, and logical consistency. Skeptical of fluff.",
            "pain_points": ["Lack of detailed plans", "Style over substance", "Vague promises"],
            "top_channels": ["Town Halls", "Policy Podcasts", "Op-Eds/Editorials"],
            "messaging_angle": "Lead with data. Use comparison charts. Prove your plan works. Avoid soundbites."
        },
        "Q2: The Partisan Champion": {
            "persona_name": "The Base Voter",
            "core_psychology": "Identifies strongly with the party/tribe. Wants a fighter, not a compromiser.",
            "pain_points": ["Perceived weakness", "Betrayal of party values", "Loss of status"],
            "top_channels": ["Rallies", "Partisan Cable News", "Direct Mail"],
            "messaging_angle": "'Us vs. Them' narrative. Show strength. Promise to fight for the team's values."
        },
        "Q3: The Honest Outsider": {
            "persona_name": "The Integrity Seeker",
            "core_psychology": "Tired of corruption and politics as usual. Votes for the 'clean' candidate.",
            "pain_points": ["Corruption", "Career politicians", "Opaque funding"],
            "top_channels": ["Grassroots Door-Knocking", "Local Radio", "Civic League Forums"],
            "messaging_angle": "'Clean house.' Radical transparency. Focus on ethics and anti-corruption."
        },
        "Q4: The Beloved Figure": {
            "persona_name": "The Personality Voter",
            "core_psychology": "Likes the candidate personally. Trusts them like a neighbor. May not know the policies.",
            "pain_points": ["Feeling ignored", "Inauthenticity", "Negative campaigning"],
            "top_channels": ["Human Interest Stories", "Social Media (Personal)", "Community Events"],
            "messaging_angle": "Focus on character, backstory, and empathy. 'A heart for the people.'"
        },
        "Q5: The Unstoppable Force": {
            "persona_name": "The Bandwagon Voter",
            "core_psychology": "Wants to back a winner. motivated by the inevitability of your victory.",
            "pain_points": ["Wasting a vote", "Being on the losing side", "Uncertainty"],
            "top_channels": ["Poll Announcements", "High-End Fundraisers", "Major Network Interviews"],
            "messaging_angle": "Project inevitability. Show polling lead. 'Join the movement that is winning.'"
        },
        "Q6: The Agitator": {
            "persona_name": "The Protest Voter",
            "core_psychology": "Angry at the system. Wants to burn it down or shake it up.",
            "pain_points": ["Status quo", "Elites", "Slow change"],
            "top_channels": ["Viral Video Clips", "Alternative Media", "Protests/Rallies"],
            "messaging_angle": "Amplify the anger. Name the enemy. Be the disruptor."
        },
        "Q7: The Ghost Candidate": {
            "persona_name": "The Disengaged Public",
            "core_psychology": "Doesn't know you exist. Likely won't vote unless mobilized.",
            "pain_points": ["Apathy", "Lack of information", "Disconnection"],
            "top_channels": ["Facebook Ads (Awareness)", "Local News", "Door-to-Door Intro"],
            "messaging_angle": "Introduction. Simple name recognition. Define the opponent before they define you."
        },
        "Q8: The Reliable Steward": {
            "persona_name": "The Pragmatic Moderate",
            "core_psychology": "Wants competent governance. Fears radical change. Values stability.",
            "pain_points": ["Chaos", "Risk", "Incompetence"],
            "top_channels": ["Newspaper Endorsements", "Debates", "Expert Panels"],
            "messaging_angle": "Experience. Stability. 'Safe hands on the wheel.' Proven track record."
        }
    }
    return targeting_profiles.get(quadrant, {
        "persona_name": "Unknown", "core_psychology": "N/A", "pain_points": ["N/A"],
        "top_channels": ["N/A"], "messaging_angle": "N/A"
    })

def generate_voter_outreach_sequence(quadrant: str, profile: dict, channel: str, api_key: str) -> str:
    if not api_key:
        return "⚠️ Please add your OpenAI API key in the sidebar."
    try:
        client = openai.OpenAI(api_key=api_key)
        prompt = f"""
        You are an elite political strategist. I am targeting the '{profile['persona_name']}' voter profile in '{quadrant}'.
        Their psychology is: {profile['core_psychology']}
        Their pain points are: {', '.join(profile['pain_points'])}
        I want to reach them using: {channel}
        Write a literal 3-step outreach sequence (e.g., Ad Hook, Landing Page Pitch, Volunteer Script) tailored for {channel}. 
        Keep it highly specific, punchy, and ready to deploy. Do not use generic political fluff. Max 200 words.
        """
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=250
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Failed to generate outreach sequence: {str(e)}"

# ------------------------------
# AI & Strategy Generators
# ------------------------------
def generate_ai_enhanced_strategy(quadrant: str, race_type: str, opponent_status: str, api_key: str) -> str:
    if not api_key:
        return "⚠️ Please add your OpenAI API Key in the sidebar to generate AI-enhanced tactics."
    try:
        client = openai.OpenAI(api_key=api_key)
        prompt = f"""
        You are a top-tier political consultant specializing in the 8-Quadrant Political Matrix.
        Create a practical, actionable 3-part strategy for a candidate in {quadrant} running in a {race_type} against an opponent who is '{opponent_status}'.
        Follow these rules strictly:
        1.  1 quick win to shift voter perception immediately
        2.  A 1-sentence stump speech soundbite
        3.  1 measurable metric to track success of this strategy
        Keep the tone direct, strategic, and tailored for political operatives. Max 200 words total.
        """
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=250
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Failed to generate AI strategy: {str(e)}"

def generate_competitive_counter_strategy(my_q: str, comp_q: str, race_type: str, api_key: str) -> str:
    if not api_key:
        return "⚠️ Please add your OpenAI API key in the sidebar."
    try:
        client = openai.OpenAI(api_key=api_key)
        prompt = f"""
        You are a ruthless opposition researcher. My candidate is in '{my_q}' and my opponent is in '{comp_q}' in a {race_type}.
        Write a literal 3-point "Attack/Contrast Strategy" explaining exactly how I can exploit the weaknesses of their quadrant. Max 150 words.
        """
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=200
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Failed to generate counter-strategy: {str(e)}"

def generate_execution_copy(quadrant: str, metric_to_boost: str, copy_type: str, race_type: str, api_key: str) -> str:
    if not api_key:
        return "⚠️ Please add your OpenAI API key in the sidebar."
    try:
        client = openai.OpenAI(api_key=api_key)
        prompt = f"""
        You are an elite speechwriter. The candidate is in '{quadrant}' in a {race_type}.
        Write a {copy_type} specifically engineered to drastically boost the '{metric_to_boost}' metric based on the 8-Quadrant framework.
        Do not use generic political speak. Use psychological triggers. Make it ready to copy/paste.
        """
        response = client.chat.completions.create(
            model="gpt-4o-mini", 
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=400
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Failed to generate copy: {str(e)}"

def audit_text_to_scores(text_input: str, api_key: str) -> tuple[NormalizedScores, str]:
    client = openai.OpenAI(api_key=api_key)
    prompt = f"""
    You are a ruthless, expert political analyst. Analyze the following campaign text and score the candidate's voter perception.
    Score each metric from 0 to 100 based STRICTLY on the evidence in the text:
    - Voter Resonance (VR) - Emotional Connection
    - Policy Viability (PV) - Perceived Value
    - Public Integrity (PI) - Trust
    - Momentum (M) - Scarcity/Urgency
    Text: \"\"\"\"{text_input}\"\"\"
    Return ONLY a JSON object: {{"voter_resonance": 0, "policy_viability": 0, "public_integrity": 0, "momentum": 0, "reasoning": "One sentence explaining your highest and lowest scores."}}
    """
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        response_format={ "type": "json_object" },
        temperature=0.3
    )
    data = json.loads(response.choices[0].message.content)
    return NormalizedScores(
        voter_resonance=data["voter_resonance"],
        policy_viability=data["policy_viability"],
        public_integrity=data["public_integrity"],
        momentum=data["momentum"]
    ), data["reasoning"]

def calculate_behavioral_scores(returning_rate: float, full_price_rate: float, review_rate: float) -> NormalizedScores:
    """
    Calculates perception scores based on raw behavioral KPIs.
    Mapping: 
    - Returning Rate -> Voter Engagement (VR)
    - Full Price Rate -> Donor Loyalty (PV)
    - Review Rate -> Volunteer Activation (PI proxy)
    """
    # Heuristics mapping 0.0-1.0 rates to 0-100 scores
    # PV: Donors giving "full price" (max donation) or recurring = High Viability/Loyalty
    pv_score = min(100, full_price_rate * 400)  
    
    # PI: Volunteers/Trust metrics
    trust_score = min(100, returning_rate * 250) 
    
    # VR: Engagement/Excitement
    ec_score = min(100, review_rate * 1000) 
    
    # Momentum: Defaulting to neutral/low
    momentum_score = 30 
    
    return NormalizedScores(ec_score, pv_score, trust_score, momentum_score)

QUADRANT_PROGRESSION = {
    "Q7: The Ghost Candidate": {"target": "Q8: The Reliable Steward", "target_scores": {"vr": 40, "pv": 75, "pi": 75, "m": 40}},
    "Q3: The Honest Outsider": {"target": "Q1: The Policy Wonk", "target_scores": {"vr": 25, "pv": 75, "pi": 50, "m": 30}},
    "Q1: The Policy Wonk": {"target": "Q5: The Unstoppable Force", "target_scores": {"vr": 75, "pv": 80, "pi": 70, "m": 50}},
    "Q6: The Agitator": {"target": "Q5: The Unstoppable Force", "target_scores": {"vr": 80, "pv": 75, "pi": 70, "m": 50}},
    "Q4: The Beloved Figure": {"target": "Q2: The Partisan Champion", "target_scores": {"vr": 75, "pv": 60, "pi": 80, "m": 50}},
    "Q8: The Reliable Steward": {"target": "Q5: The Unstoppable Force", "target_scores": {"vr": 75, "pv": 85, "pi": 80, "m": 60}},
    "Q2: The Partisan Champion": {"target": "Q5: The Unstoppable Force", "target_scores": {"vr": 85, "pv": 80, "pi": 80, "m": 60}},
    "Q5: The Unstoppable Force": {"target": "Summit (Landlide Victory)", "target_scores": {"vr": 90, "pv": 90, "pi": 90, "m": 90}},
    "Unclassified Quadrant": {"target": "Q8: The Reliable Steward", "target_scores": {"vr": 50, "pv": 70, "pi": 70, "m": 40}}
}

# ------------------------------
# PROPRIETARY RACE DYNAMIC THRESHOLDS
# ------------------------------
BASE_HIGH_THRESHOLD = 70
BASE_LOW_THRESHOLD = 30

RACE_WEIGHTS = {
    "Local Municipal": {"vr": -5, "pv": 0, "pi": 10, "momentum": -5},
    "State Legislature": {"vr": 0, "pv": 5, "pi": 5, "momentum": 0},      
    "Governor/Congress": {"vr": 10, "pv": 5, "pi": 5, "momentum": 10},   
    "Senate/President": {"vr": 15, "pv": 0, "pi": 0, "momentum": 15},
    "Primary Election": {"vr": 10, "pv": -5, "pi": -5, "momentum": 10},
    "General Election": {"vr": 0, "pv": 5, "pi": 10, "momentum": 0}
}

def calculate_dynamic_thresholds(race_type: str) -> dict:
    weights = RACE_WEIGHTS.get(race_type, RACE_WEIGHTS["General Election"])
    final_thresholds = {}
    
    for metric in ["vr", "pv", "pi", "momentum"]:
        raw_high = BASE_HIGH_THRESHOLD + weights[metric]
        raw_low = BASE_LOW_THRESHOLD + weights[metric]
        
        h = max(55, min(90, raw_high))
        l = min(45, max(10, raw_low))
        
        if (h - l) < 20:
            mid_point = (h + l) / 2
            h = mid_point + 10
            l = mid_point - 10
            
        final_thresholds[f"high_{metric}"] = int(h)
        final_thresholds[f"low_{metric}"] = int(l)
        
    return final_thresholds

def generate_roadmap(current_quadrant: str, current_scores: NormalizedScores, race_type: str, api_key: str) -> tuple[str, dict, str]:
    progression = QUADRANT_PROGRESSION.get(current_quadrant, QUADRANT_PROGRESSION["Unclassified Quadrant"])
    target = progression["target"]
    t_scores = progression["target_scores"]
    
    gaps = {
        "VR": t_scores["vr"] - current_scores.voter_resonance,
        "PV": t_scores["pv"] - current_scores.policy_viability,
        "PI": t_scores["pi"] - current_scores.public_integrity,
        "Momentum": t_scores["m"] - current_scores.momentum
    }
    
    client = openai.OpenAI(api_key=api_key)
    prompt = f"""
    You are a campaign manager for a winning candidate. A candidate in the {race_type} race is currently in "{current_quadrant}".
    Their scores are: VR={current_scores.voter_resonance}, PV={current_scores.policy_viability}, PI={current_scores.public_integrity}, Momentum={current_scores.momentum}.
    The mathematical gaps to reach the target zone ("{target}") are: VR: {gaps['VR']} pts, PV: {gaps['PV']} pts, PI: {gaps['PI']} pts, Momentum: {gaps['Momentum']} pts.
    Write a highly specific, 3-step bridge strategy to close the LARGEST negative gaps. Focus on actionable messaging, policy pivots, or GOTV operations. No fluff. Max 150 words.
    """
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=200
    )
    return target, gaps, response.choices[0].message.content.strip()

# ------------------------------
# Base Built-In & Field Strategies
# ------------------------------
@st.cache_data
def get_base_strategy(quadrant: str, race_type: str) -> dict:
    strategies = {
        "Q1: The Policy Wonk": {"core_focus": "Build emotional connection with voters while preserving policy strength", "actions": ["Launch a storytelling ad campaign", "Highlight personal background", "Hold emotional town halls", "Deploy surrogates to humanize candidate"]},
        "Q2: The Partisan Champion": {"core_focus": "Expand reach beyond the base by building trust with independents", "actions": ["Focus on 'kitchen table' issues", "Highlight bipartisan endorsements", "Soften rhetorical edges in ads", "Target swing districts with economic message"]},
        "Q3: The Honest Outsider": {"core_focus": "Define a platform and increase name ID", "actions": ["Release detailed policy blueprint", "Secure major editorial endorsements", "Piggyback on major party events", "Introduce via biographical ads"]},
        "Q4: The Beloved Figure": {"core_focus": "Transition from 'nice person' to 'competent leader'", "actions": ["Roll out detailed plans", "Secure expert endorsements", "Highlight professional accomplishments", "Contrast competence with opponent chaos"]},
        "Q5: The Unstoppable Force": {"core_focus": "Protect the lead and maximize turnout", "actions": ["Focus on GOTV (Get Out The Vote)", "Protect against complacency", "Expand map into opponent territory", "Raise money for down-ballot support"]},
        "Q6: The Agitator": {"core_focus": "Pivot from protest to solutions to win over skeptics", "actions": ["Release 'Contract with Voters'", "Gain credibility via debates", "Highlight specific policy wins", "Tone down rhetoric for general election"]},
        "Q7: The Ghost Candidate": {"core_focus": "Survival and name recognition", "actions": ["Intensive social media content", "Grassroots volunteer drive", "Targeted local media buys", "Door-to-door visibility"]},
        "Q8: The Reliable Steward": {"core_focus": "Inject energy and vision into the campaign", "actions": ["Reframe race as a 'fight for the future'", "Energetic rally schedule", "Youth outreach programs", "Bold vision statements"]}
    }
    return strategies.get(quadrant, {"core_focus": "No strategy found", "actions": []})

def get_field_strategy(quadrant: str) -> dict:
    strategies = {
        "Q1: The Policy Wonk": {"canvass_script": "Focus on data and plans", "volunteer_focus": "Policy experts/Surrogates", "event_type": "Town Halls/Forums", "rationale": "Voters want substance."},
        "Q2: The Partisan Champion": {"canvass_script": "Us vs. Them / The Fight", "volunteer_focus": "Party Loyalists", "event_type": "Rallies", "rationale": "Mobilize the base."},
        "Q3: The Honest Outsider": {"canvass_script": "Clean house / Change", "volunteer_focus": "Reform Advocates", "event_type": "Meet & Greets", "rationale": "Intimacy builds trust."},
        "Q4: The Beloved Figure": {"canvass_script": "Character & Heart", "volunteer_focus": "Community Leaders", "event_type": "Service Projects", "rationale": "Show, don't just tell."},
        "Q5: The Unstoppable Force": {"canvass_script": "Momentum / Winning Team", "volunteer_focus": "Data/ GOTV Ops", "event_type": "Large Rallies", "rationale": "Bandwagon effect."},
        "Q6: The Agitator": {"canvass_script": "Outrage / The Enemy", "volunteer_focus": "Activists", "event_type": "Protests / Pop-ups", "rationale": "Channel anger."},
        "Q7: The Ghost Candidate": {"canvass_script": "Introduction / Identity", "volunteer_focus": "Friends & Family", "event_type": "Door Knocking", "rationale": "Build presence from zero."},
        "Q8: The Reliable Steward": {"canvass_script": "Experience / Stability", "volunteer_focus": "Professionals/Experts", "event_type": "Roundtables", "rationale": "Reinforce competence."}
    }
    return strategies.get(quadrant, {"canvass_script": "Standard", "volunteer_focus": "N/A", "event_type": "Standard", "rationale": "N/A"})

# ------------------------------
# Drift Check Functions
# ------------------------------
def check_universal_health(metrics: dict) -> str:
    alerts = []
    if metrics.get('negative_rating', 0) > 0.6:
        alerts.append("⚠️ **FAVORABILITY TRAP:** Unfavorability > 60%. You are alienating the electorate.")
    if metrics.get('volunteer_retention', 0) < 0.15:
        alerts.append("📉 **ENTHUSIASM LEAK:** Volunteer retention < 15%. The base is not inspired.")
    if metrics.get('donation_rate', 0) < 0.05:
        alerts.append("📉 **VIABILITY WARNING:** Donation conversion < 5%. Voters don't think you can win.")
    if metrics.get('volunteer_retention', 0) > 0.4:
        alerts.append("🚀 **SURGE:** Volunteer retention > 40%. You have a movement.")
    if metrics.get('donation_rate', 0) > 0.2:
        alerts.append("🚀 **FUNDS SUCCESS:** Donation rate > 20%. High voter buy-in.")
    return "\n\n".join(alerts) if alerts else "✅ **Healthy Baselines:** Campaign metrics are stable."

def check_behavioral_alignment(current_quadrant: str, current_metrics: dict) -> str:
    alert = None
    q = current_quadrant
    # Logic adapted for politics
    if q == "Q1: The Policy Wonk" and current_metrics.get('negative_rating', 0) > 0.6:
        alert = "⚠️ **MISALIGNED:** You are Q1, but high negatives suggest voters dislike you personally, not just your policies."
    elif q == "Q2: The Partisan Champion" and current_metrics.get('volunteer_retention', 1) < 0.2:
        alert = "⚠️ **MISALIGNED:** You claim to be a Champion, but your base is leaving."
    elif q == "Q3: The Honest Outsider" and current_metrics.get('donation_rate', 0) > 0.15:
        alert = "🚀 **GRADUATING:** You are Q3, but strong fundraising indicates you are becoming a Q1 or Q8 contender."
    elif q == "Q5: The Unstoppable Force" and current_metrics.get('volunteer_retention', 0) < 0.4:
        alert = "⚠️ **MISALIGNED:** You claim inevitability, but enthusiasm is low. Risk of collapse."
    return alert if alert else "✅ **ALIGNED:** Metrics match quadrant."

def check_momentum_trend(past_metrics: dict, current_metrics: dict) -> str:
    delta_neg = current_metrics.get('negative_rating', 0) - past_metrics.get('negative_rating', 0)
    delta_vol = current_metrics.get('volunteer_retention', 0) - past_metrics.get('volunteer_retention', 0)
    delta_don = current_metrics.get('donation_rate', 0) - past_metrics.get('donation_rate', 0)
    
    trends = []
    if delta_neg > 0.15:
        trends.append(f"📉 **Negative Momentum:** Unfavorables grew by +{delta_neg*100:.1f}%.")
    if delta_vol < -0.15:
        trends.append(f"📉 **Negative Momentum:** Volunteer retention dropped by {delta_vol*100:.1f}%.")
    if delta_don > 0.10:
        trends.append(f"📈 **Positive Momentum:** Donation rate grew by +{delta_don*100:.1f}%.")
    if delta_vol > 0.15:
        trends.append(f"📈 **Positive Momentum:** Volunteer retention grew by +{delta_vol*100:.1f}%.")
    if not trends:
        return "⚖️ **Stable:** No significant momentum shifts detected."
    return "\n\n".join(trends)

# ------------------------------
# Advanced Strategy Functions
# ------------------------------
def calculate_budget_allocation(quadrant: str, race_type: str) -> dict:
    allocations = {
        "Q7: The Ghost Candidate": {"Field (Ground Game)": 80, "Ads (Awareness)": 10, "Digital (Engagement)": 10},
        "Q3: The Honest Outsider": {"Field (Ground Game)": 60, "Ads (Bio/Intro)": 30, "Digital (Engagement)": 10},
        "Q6: The Agitator": {"Ads (Contrast)": 70, "Digital (Viral)": 20, "Field (Rallies)": 10},
        "Q1: The Policy Wonk": {"Ads (Policy Details)": 20, "Field (Town Halls)": 30, "Digital (Persuasion)": 50},
        "Q8: The Reliable Steward": {"Ads (Endorsements)": 40, "Field (Surrogates)": 40, "Digital (Turnout)": 20},
        "Q4: The Beloved Figure": {"Field (Community)": 20, "Ads (Bio Story)": 20, "Digital (Shareable)": 60},
        "Q2: The Partisan Champion": {"Field (GOTV)": 30, "Ads (Rally Base)": 20, "Digital (Attack/Defend)": 50},
        "Q5: The Unstoppable Force": {"Field (Turnout Ops)": 40, "Ads (Landslide)": 30, "Digital (Celebration)": 30}
    }
    return allocations.get(quadrant, {"Field": 33, "Ads": 33, "Digital": 34})

def calculate_pricing_elasticity(pv_score: float, momentum_score: float, base_ask: float) -> dict:
    # Renamed for fundraising context
    pv_multiplier = 1.0 + (pv_score / 100)
    if pv_score >= 50 and momentum_score >= 70:
        momentum_multiplier = 1.0 + ((momentum_score - 50) / 100)
    else:
        momentum_multiplier = 1.0 
        
    optimal_ask = base_ask * pv_multiplier * momentum_multiplier
    
    return {
        "Optimal 'Max Ask'": f"${optimal_ask:.2f}",
        "Strategy": "Push high-dollar donors with access offers" if momentum_multiplier > 1.0 else "Focus on small-dollar grassroots fundraising."
    }

def generate_team_action_plan(candidate_q: str, manager_q: str, api_key: str) -> str:
    if not api_key: return "⚠️ API Key required."
    try:
        client = openai.OpenAI(api_key=api_key)
        prompt = f"""
        The Candidate sees themselves as '{candidate_q}'. The Campaign Manager sees the race as '{manager_q}'.
        Write a 3-step plan to resolve this internal disconnect. Focus on aligning the stump speech with the field strategy. Max 100 words.
        """
        response = client.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}], max_tokens=150, temperature=0.7)
        return response.choices[0].message.content.strip()
    except Exception as e:
        return str(e)

def generate_launch_smokescreen(hypothesis_q: str, problem: str, audience: str, api_key: str) -> str:
    if not api_key: return "⚠️ API Key required."
    try:
        client = openai.OpenAI(api_key=api_key)
        prompt = f"We are launching a campaign. We want to artificially position the candidate in {hypothesis_q}. The core community problem is: {problem}. The target voters are: {audience}. Write a highly converting 'Exploratory Committee' or 'Launch' email copy. Do NOT list policy details. Sell the vision and the fight. Include a strong headline, 3 bullet points of pain, and the CTA to join the movement."
        response = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], temperature=0.8, max_tokens=500)
        return response.choices[0].message.content.strip()
    except Exception as e: return str(e)

# ------------------------------
# Visualization & Reporting Tools
# ------------------------------
def render_performance_chart(scores: NormalizedScores):
    metric_data = pd.DataFrame({
        "Core Matrix Dimension": ["Voter Resonance (Axis)", "Policy Viability (Axis)", "Public Integrity (Axis)", "Momentum (Lever)"],
        "Score (0-100)": [scores.voter_resonance, scores.policy_viability, scores.public_integrity, scores.momentum]
    })
    fig = px.bar(metric_data, x="Core Matrix Dimension", y="Score (0-100)", color="Score (0-100)", color_continuous_scale="Reds", range_y=[0, 100], title="Current Voter Perception Scores")
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

def render_radar_chart(scores: NormalizedScores, title="Voter Perception Profile"):
    df = pd.DataFrame({
        'Metric': ['Voter Resonance', 'Policy Viability', 'Public Integrity', 'Momentum'],
        'Score': [scores.voter_resonance, scores.policy_viability, scores.public_integrity, scores.momentum]
    })
    fig = px.line_polar(df, r='Score', theta='Metric', line_close=True, title=title)
    fig.update_traces(fill='toself', line_color="rgb(220, 53, 69)", fillcolor="rgba(220, 53, 69, 0.3)") # Red/Political color
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])))
    st.plotly_chart(fig, use_container_width=True)

def render_3d_matrix(scores: NormalizedScores, thresholds: dict):
    fig = go.Figure()
    fig.add_trace(go.Scatter3d(
        x=[scores.policy_viability], y=[scores.public_integrity], z=[scores.voter_resonance],
        mode='markers+text', text=['Your Candidate'], textposition='top center',
        marker=dict(size=15, color='rgb(220, 53, 69)', symbol='diamond')
    ))
    fig.update_layout(
        scene=dict(
            xaxis_title='Policy Viability (PV)', yaxis_title='Public Integrity (PI)', zaxis_title='Voter Resonance (VR)',
            xaxis=dict(range=[0, 100]), yaxis=dict(range=[0, 100]), zaxis=dict(range=[0, 100])
        ),
        title="3-Axis Political Perception Matrix", margin=dict(l=0, r=0, b=0, t=40)
    )
    st.plotly_chart(fig, use_container_width=True)

def render_timeline(campaign_name: str):
    history = st.session_state.score_history.get(campaign_name, [])
    if len(history) < 2:
        st.info("Not enough data points yet. Assess this campaign again in 2 weeks to see momentum.")
        return
    df = pd.DataFrame(history)
    fig = px.line(df, x='date', y=['vr', 'pv', 'pi', 'momentum'], title=f"Campaign Momentum Timeline: {campaign_name}", labels={"value": "Score", "variable": "Metric"})
    st.plotly_chart(fig, use_container_width=True)

def generate_pdf_report(campaign_data: dict, thresholds: dict) -> io.BytesIO:
    campaign_name = campaign_data["name"]
    quadrant = campaign_data["quadrant"]
    scores = campaign_data["scores"] 
    strategy = campaign_data["strategy"]
    ai_tactics = campaign_data.get("ai_tactics", "")

    pdf = FPDF("portrait", "mm", "letter")
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, txt="Political Strategy Matrix Report", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, txt="Campaign Information", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, txt=f"Candidate/Campaign: {campaign_name}", ln=True)
    pdf.cell(0, 10, txt=f"Date: {datetime.today().strftime('%Y-%m-%d')}", ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, txt="Quadrant Classification", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, txt=f"Current Quadrant: {quadrant}", ln=True)
    score_text = (f"Scores: VR={scores.voter_resonance}, PV={scores.policy_viability}, PI={scores.public_integrity}, Momentum={scores.momentum}")
    pdf.cell(0, 10, txt=score_text, ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, txt="Winning Strategy", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, txt=f"Core Focus: {strategy.get('core_focus', 'N/A')}", ln=True)
    pdf.cell(0, 10, txt="Recommended Actions:", ln=True)
    for idx, action in enumerate(strategy.get("actions", [])):
        pdf.cell(0, 10, txt=f"  {idx+1}. {action}", ln=True)
    if ai_tactics:
        pdf.ln(5)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, txt="AI-Enhanced Tactics", ln=True)
        pdf.set_font("Arial", "", 10)
        safe_text = ai_tactics.encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 8, txt=safe_text)
    ops_strategy = get_field_strategy(quadrant)
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, txt="Field Operations", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, txt=f"Event Type: {ops_strategy['event_type']}", ln=True)
    pdf.cell(0, 10, txt=f"Volunteer Focus: {ops_strategy['volunteer_focus']}", ln=True)
    pdf.cell(0, 10, txt=f"Rationale: {ops_strategy['rationale']}", ln=True)
    pdf_bytes = pdf.output()
    return io.BytesIO(pdf_bytes)
    
# ------------------------------
# Main Interactive Tabbed Interface
# ------------------------------
def main():
    with st.sidebar:
        st.header("⚙️ Campaign Settings")
        st.session_state.openai_api_key = st.text_input("OpenAI API Key (Required for AI)", type="password", help="Get a key from platform.openai.com", value=st.session_state.openai_api_key)
        
        selected_race_type = st.selectbox("Select Race Type", ["Local Municipal", "State Legislature", "Governor/Congress", "Senate/President", "Primary Election", "General Election"])
        
        auto_thresholds = calculate_dynamic_thresholds(selected_race_type)
        
        if st.session_state.custom_thresholds != auto_thresholds:
            st.session_state.custom_thresholds = auto_thresholds
        
        st.markdown("---")
        with st.expander("📚 Matrix Logic"):
            st.caption("Uses a 3-Axis Binary Model. Thresholds auto-calibrate based on race intensity.")
            
        st.markdown("---")
        with st.expander("🎚️ Advanced Threshold Overrides"):
            st.caption("⚠️ Modifying these manually will override the race algorithms.")
            t_col1, t_col2 = st.columns(2)
            with t_col1:
                high_val = st.number_input("High Threshold", min_value=50, max_value=90, value=auto_thresholds["high_vr"], key="th_high")
            with t_col2:
                low_val = st.number_input("Low Threshold", min_value=10, max_value=49, value=auto_thresholds["low_vr"], key="th_low")

            st.session_state.custom_thresholds = {
                "high_pv": high_val, "low_pv": low_val,
                "high_vr": high_val, "low_vr": low_val,
                "high_pi": high_val, "low_pi": low_val,
                "high_momentum": high_val
            }

        st.markdown("---")
        with st.expander("💾 Data Persistence"):
            st.caption("Save/Load state to prevent data loss on app reload.")
            json_state = json.dumps({
                "saved_campaigns": [{**p, "scores": {"voter_resonance": p["scores"].voter_resonance, "policy_viability": p["scores"].policy_viability, "public_integrity": p["scores"].public_integrity, "momentum": p["scores"].momentum}} for p in st.session_state.saved_campaigns],
                "score_history": st.session_state.score_history,
                "tasks": st.session_state.tasks
            }, default=str)
            st.download_button("Download State (JSON)", data=json_state, file_name="political_matrix_state.json", mime="application/json")
            uploaded_file = st.file_uploader("Upload State (JSON)", type="json", key="json_upload")
            if uploaded_file:
                try:
                    load_data = json.load(uploaded_file)
                    for p in load_data.get("saved_campaigns", []):
                        p["scores"] = NormalizedScores(**p["scores"])
                    st.session_state.saved_campaigns = load_data.get("saved_campaigns", [])
                    st.session_state.score_history = load_data.get("score_history", {})
                    st.session_state.tasks = load_data.get("tasks", [])
                    st.success("State loaded successfully!")
                except Exception as e:
                    st.error(f"Failed to load: {e}")

    tab_home, tab_disrupt, tab_classify, tab_targeting, tab_copy, tab_prelaunch_center, tab_pricing, tab_team, tab_dashboard, tab_timeline, tab_momentum_sim, tab_tasks, tab_benchmark, tab_reports = st.tabs([
        "🏠 Home", "🧠 AI Audit & Roadmap", "🎯 Manual Assessment", "🎯 Voter Profiler", "✍️ Speech Copy Generator", 
        "🚀 Campaign Launch", "🧬 Budget & Fundraising", "🤝 Team Alignment", 
        "📊 Command Dashboard", "📈 Timeline", "⚡ Momentum Sim", 
        "✅ Task Tracker", "🏆 Opposition Research", "📄 Reports & Exports"
    ])

    with tab_home:
        st.header("Welcome to the Political Quadrant Strategy Tool")
        st.markdown("""This tool helps you: 
        1. **Identify exact voter perception** via 3-Axis mathematical modeling
        2. **Maximize voter turnout** in your current quadrant
        3. **Transition to winning positions** using AI Golden Path roadmaps
        4. **Target ideal voters** based on psychological profiles""")
        
        st.markdown("---")
        st.subheader("🎓 Understanding the 8 Zones of Voter Psychology")
        st.caption("*Our proprietary framework classifies candidates not just by polls, but by the hidden psychological state of the electorate.*")
        
        col_ed1, col_ed2 = st.columns(2)
        
        with col_ed1:
            with st.expander("📉 The Struggle Zones (Low Polling / High Effort)", expanded=False):
                st.markdown("""
                **Q7. The Ghost Candidate** | *The Symptom:* No name ID, no connection. | *The Primary Goal:* Survival & Recognition.
                **Q3. The Honest Outsider** | *The Symptom:* Good reputation, but unknown or seen as "not ready". | *The Primary Goal:* Define a platform.
                **Q6. The Agitator** | *The Symptom:* Loud, viral, but polarizing or scary to moderates. | *The Primary Goal:* Pivot to solutions.
                """)
        with col_ed2:
            with st.expander("📈 The Growth Zones (High Logic / Low Emotion)", expanded=False):
                st.markdown("""
                **Q1. The Policy Wonk** | *The Symptom:* Smart but boring. Voters say "I like your ideas but..." | *The Primary Goal:* Forge emotional connection.
                **Q8. The Reliable Steward** | *The Symptom:* Competent, trusted, but lacks "fire". | *The Primary Goal:* Inspire and mobilize.
                **Q4. The Beloved Figure** | *The Symptom:* Everyone likes you, but doubts your grit/policy. | *The Primary Goal:* Demonstrate strength/substance.
                """)
        with st.expander("🏆 The Summit Zones (High Polling / High Turnout)", expanded=False):
            st.markdown("""
            **Q2. The Partisan Champion** | *The Symptom:* Base loves you, opponents fear you. | *The Primary Goal:* Expand to the center.
            **Q5. The Unstoppable Force (The Ultimate Goal)** | *The Symptom:* Landslide potential. High trust, high emotion, high policy. | *The Primary Goal:* Run up the score.
            """)
        
        st.markdown("---")
        st.subheader("Try a Live Demo")
        if st.button("Load Demo: Incumbent Mayor"):
            st.session_state.demo_campaign = NormalizedScores(40, 80, 90, 30)
            st.rerun()

        if st.session_state.demo_campaign is not None:
            demo_quadrant, demo_thresh = classify_quadrant(st.session_state.demo_campaign, st.session_state.custom_thresholds)
            st.success(f"✅ Demo Candidate Classified as: {demo_quadrant}")
            render_radar_chart(st.session_state.demo_campaign, title="Demo Candidate Perception Profile")
            render_3d_matrix(st.session_state.demo_campaign, demo_thresh)
            strategy = get_base_strategy(demo_quadrant, selected_race_type)
            st.info(f"**Strategy Focus:** {strategy['core_focus']}")

    with tab_disrupt:
        st.header("🧠 AI-Powered Campaign Audit & Roadmap")
        if not st.session_state.openai_api_key:
            st.error("⚠️ You must enter your OpenAI API Key in the sidebar to use this feature.")
        else:
            with st.form("audit_form"):
                audit_name = st.text_input("Candidate Name")
                audit_text = st.text_area("Paste campaign text here:", height=250, placeholder="Paste a speech transcript, campaign website About page, or recent press release...")
                audit_submitted = st.form_submit_button("🔥 Run AI Audit & Generate Roadmap")
                
                if audit_submitted and audit_name and len(audit_text) > 50:
                    with st.spinner("AI is analyzing voter perception..."):
                        try:
                            scores, reasoning = audit_text_to_scores(audit_text, st.session_state.openai_api_key)
                            quadrant, thresholds = classify_quadrant(scores, st.session_state.custom_thresholds)
                            
                            with st.spinner("Calculating Golden Path Roadmap..."):
                                target_q, score_gaps, roadmap_strategy = generate_roadmap(quadrant, scores, selected_race_type, st.session_state.openai_api_key)
                            
                            strategy = get_base_strategy(quadrant, selected_race_type)
                            campaign_data = {"name": audit_name, "quadrant": quadrant, "scores": scores, "strategy": strategy, "ai_tactics": roadmap_strategy, "thresholds": thresholds}
                            st.session_state.saved_campaigns.append(campaign_data)
                            st.session_state.latest_quadrant = quadrant

                            if audit_name not in st.session_state.score_history: st.session_state.score_history[audit_name] = []
                            st.session_state.score_history[audit_name].append({"date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "vr": scores.voter_resonance, "pv": scores.policy_viability, "pi": scores.public_integrity, "momentum": scores.momentum})
                            
                            st.success(f"✅ Analysis Complete: {quadrant}")
                            st.info(f"**AI Reasoning:** {reasoning}")
                            render_performance_chart(scores)
                            
                            st.markdown("---")
                            st.subheader("🛤️ The Golden Path Roadmap")
                            col_r1, col_r2 = st.columns([1, 2])
                            with col_r1:
                                st.metric("Current State", quadrant.split(":")[0])
                                st.markdown(f"#### ➡️ Target State\n**{target_q}**")
                                st.markdown("**Score Gaps to Close:**")
                                for metric, gap in score_gaps.items():
                                    color = "red" if gap > 0 else "green"
                                    st.markdown(f"<span style='color:{color}'>{metric}: {'+' if gap > 0 else ''}{gap} pts</span>", unsafe_allow_html=True)
                            with col_r2:
                                st.markdown("#### 🚀 The Bridge Strategy")
                                st.write(roadmap_strategy)
                        except Exception as e:
                            st.error(f"Failed to process: {str(e)}")

    with tab_classify:
        st.header("Assess Your Campaign via Questionnaire")
        
        with st.form("classification_form"):
            prod_name = st.text_input("Candidate/Campaign Name")
            
            calculated_scores = {}
            for dimension, questions in MATRIX_QUESTIONS.items():
                with st.expander(f"{'⚡' if 'Momentum' in dimension else '🏛️'} {dimension}", expanded=False):
                    dimension_responses = []
                    for q in questions:
                        answer = st.radio(label=q, options=[1, 2, 3, 4, 5], format_func=lambda x: {1: "Strongly Disagree", 2: "Disagree", 3: "Neutral", 4: "Agree", 5: "Strongly Agree"}[x], index=2, key=f"{prod_name}_{q}")
                        dimension_responses.append(answer)
                    avg_score = sum(dimension_responses) / len(dimension_responses)
                    calculated_scores[dimension] = round(avg_score * 20)
            
            st.markdown("---")
            use_data = st.checkbox("📊 Override subjective scores with hard Campaign Data (Recommended)", key="use_data_override")
            
            ret_p = 0.0
            fp_p = 0.0
            rev_p = 0.0
            
            if use_data:
                st.info("Input real metrics below. If filled, the app will mathematically calculate your true position.")
                c1, c2, c3 = st.columns(3)
                with c1: ret_p = st.number_input("Volunteer Retention Rate (%)", 0.0, 100.0, 10.0, step=0.5, key="d_ret") / 100
                with c2: fp_p = st.number_input("Max/Recurring Donation Rate (%)", 0.0, 100.0, 2.0, step=0.5, key="d_fp") / 100
                with c3: rev_p = st.number_input("Social Engagement Rate (%)", 0.0, 100.0, 5.0, step=0.5, key="d_rev") / 100
            
            submitted = st.form_submit_button("Analyze Campaign")
            
            if submitted and prod_name:
                if use_data and (ret_p > 0 or fp_p > 0 or rev_p > 0):
                    scores = calculate_behavioral_scores(ret_p, fp_p, rev_p)
                    st.success("✅ Using Data-Driven Behavioral Scores.")
                else:
                    scores = NormalizedScores(
                        voter_resonance=calculated_scores["Voter Resonance (VR) - *Emotional Connection*"],
                        policy_viability=calculated_scores["Policy Viability (PV) - *Perceived Value*"],
                        public_integrity=calculated_scores["Public Integrity (PI) - *Trust*"],
                        momentum=calculated_scores["Campaign Momentum (M) - *Strategy Lever*"]
                    )
                
                quadrant, thresholds = classify_quadrant(scores, st.session_state.custom_thresholds)
                strategy = get_base_strategy(quadrant, selected_race_type)
                
                with st.spinner("Generating AI Tactics..."):
                    ai_tactics = generate_ai_enhanced_strategy(quadrant, selected_race_type, "Unknown", st.session_state.openai_api_key)
                
                campaign_data = {"name": prod_name, "quadrant": quadrant, "scores": scores, "strategy": strategy, "ai_tactics": ai_tactics, "thresholds": thresholds}
                st.session_state.saved_campaigns.append(campaign_data)
                st.session_state.latest_quadrant = quadrant

                if prod_name not in st.session_state.score_history: st.session_state.score_history[prod_name] = []
                st.session_state.score_history[prod_name].append({"date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "vr": scores.voter_resonance, "pv": scores.policy_viability, "pi": scores.public_integrity, "momentum": scores.momentum})
                
                st.subheader(f"Results for {prod_name}")
                st.markdown(f"### {quadrant}")
                render_performance_chart(scores)
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown("#### 🏛️ Core Strategy")
                    st.write(f"**Focus:** {strategy['core_focus']}")
                    st.write("**Actions:**")
                    for action in strategy['actions']:
                        st.write(f"- {action}")
                with col_b:
                    st.markdown("#### 🤖 AI-Enhanced Tactics")
                    st.write(ai_tactics)

                st.markdown("---")
                st.subheader("🚜 Field Operations Synchronization")
                ops_strategy = get_field_strategy(quadrant)
                op_col1, op_col2, op_col3 = st.columns(3)
                with op_col1:
                    st.metric("Event Type", ops_strategy['event_type'])
                with op_col2:
                    st.metric("Volunteer Focus", ops_strategy['volunteer_focus'])
                with op_col3:
                    st.info(f"**Rationale:** {ops_strategy['rationale']}")
                
                if quadrant == "Q7: The Ghost Candidate":
                    st.warning("⚠️ **Field Alert:** Recommendation is Intensive Door-Knocking.")

        if st.session_state.latest_quadrant:
            st.markdown("---")
            st.subheader("📈 Campaign Health Drift Check")
            
            with st.expander("⚡ Universal Health Check"):
                u_neg = st.slider("Unfavorability Rating (%)", 0, 100, 20, key="uni_neg") / 100
                u_vol = st.slider("Volunteer Retention Rate (%)", 0, 100, 20, key="uni_vol") / 100
                u_don = st.slider("Donation Conversion Rate (%)", 0, 100, 5, key="uni_don") / 100
                universal_metrics = {"negative_rating": u_neg, "volunteer_retention": u_vol, "donation_rate": u_don}
                if st.button("Check Universal Health", key="uni_btn"):
                    st.markdown(check_universal_health(universal_metrics))

    with tab_targeting:
        st.header("🎯 Voter Profiler & Targeting Engine")
        st.markdown("Stop campaigning to 'everyone'. Each quadrant has a specific voter psychology. Find *who* to target and *what* to say.")
        
        default_q_index = 0
        all_quadrants = list(QUADRANT_PROGRESSION.keys())
        
        if st.session_state.latest_quadrant and st.session_state.latest_quadrant in all_quadrants:
            default_q_index = all_quadrants.index(st.session_state.latest_quadrant)
            st.success(f"✅ Auto-loaded profile for your latest assessment: **{st.session_state.latest_quadrant}**")
        
        selected_q = st.selectbox("Select a Quadrant to Profile", all_quadrants, index=default_q_index)
        profile = get_voter_targeting_strategy(selected_q)
        
        col1, col2 = st.columns([1, 2])
        with col1:
            st.subheader(f"🧠 {profile['persona_name']}")
            st.info(profile['core_psychology'])
            
            st.markdown("---")
            st.markdown("**💔 Core Pain Points**")
            for pain in profile['pain_points']:
                st.write(f"• {pain}")
                
        with col2:
            st.markdown("#### 📡 Top Acquisition Channels")
            for channel in profile['top_channels']:
                st.write(f"➡️ {channel}")
            
            st.markdown("---")
            st.markdown("#### 💬 Psychological Messaging Angle")
            st.success(profile['messaging_angle'])
            
        st.markdown("---")
        st.subheader("🤖 AI Multi-Touch Outreach Generator")
        if not st.session_state.openai_api_key:
            st.error("⚠️ Requires API Key.")
        else:
            with st.form("outreach_form"):
                target_channel = st.selectbox("Choose a primary channel to generate a sequence for", profile['top_channels'])
                if st.form_submit_button("Generate 3-Step Outreach Sequence"):
                    with st.spinner("Writing psychological outreach sequence..."):
                        sequence = generate_voter_outreach_sequence(selected_q, profile, target_channel, st.session_state.openai_api_key)
                        st.text_area("Outreach Sequence", value=sequence, height=250)

    with tab_copy:
        st.header("✍️ AI Speech & Ad Copy Generator")
        if not st.session_state.openai_api_key:
            st.error("⚠️ You must enter your OpenAI API Key in the sidebar.")
        else:
            with st.form("copy_form"):
                c1, c2 = st.columns(2)
                with c1:
                    current_q = st.selectbox("Your Current Quadrant", [q for q in QUADRANT_PROGRESSION.keys()])
                    metric_boost = st.selectbox("Metric to Boost", ["Voter Resonance", "Policy Viability", "Public Integrity", "Momentum"])
                with c2:
                    copy_type = st.selectbox("Asset Type", ["Stump Speech Soundbite", "Press Release Quote", "Debate Closing Statement", "Social Media Post", "Email Subject Line & Body"])
                if st.form_submit_button("✨ Generate Copy"):
                    with st.spinner("Writing high-converting political copy..."):
                        st.text_area("Copy to Clipboard", value=generate_execution_copy(current_q, metric_boost, copy_type, selected_race_type, st.session_state.openai_api_key), height=300)

    with tab_prelaunch_center:
        st.header("🚀 Campaign Launch Center")
        st.markdown("Plan your entry into the race using theoretical simulations and perception engineering.")
        
        prelaunch_subtabs = st.tabs(["🎯 Launch Simulator", "🧠 Perception Engineer"])
        
        with prelaunch_subtabs[0]:
            st.subheader("Pre-Launch Simulation & Strategy")
            st.markdown("Use the sliders to set your target launch scores and see the predicted quadrant outcome.")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Target Scores**")
                t_vr = st.slider("Target VR", 0, 100, 70, key="t_vr")
                t_pv = st.slider("Target PV", 0, 100, 80, key="t_pv")
                t_pi = st.slider("Target PI", 0, 100, 60, key="t_pi")
                t_momentum = st.slider("Target Momentum", 0, 100, 40, key="t_momentum")
            with col2:
                st.markdown("**Projected Outcome**")
                target_scores = NormalizedScores(t_vr, t_pv, t_pi, t_momentum)
                projected_quadrant, _ = classify_quadrant(target_scores, st.session_state.custom_thresholds)
                st.metric("Projected Quadrant", projected_quadrant) 
                if st.button("Generate Full Launch Plan", key="sim_plan_btn"):
                    strategy = get_base_strategy(projected_quadrant, selected_race_type)
                    st.write("**Recommended Launch Actions:**")
                    for action in strategy['actions']:
                        st.write(f"- {action}")
                    if st.session_state.openai_api_key:
                        with st.spinner("Generating AI Roadmap..."):
                            st.write(generate_ai_enhanced_strategy(projected_quadrant, selected_race_type, "Primary Opponent", st.session_state.openai_api_key))

        with prelaunch_subtabs[1]:
            st.subheader("Pre-Launch Perception Engineer")
            st.markdown("Don't guess your launch scores. **Engineer them.** Choose a psychological lever, test it with a smokescreen landing page, and reverse-engineer your true starting line.")
            if not st.session_state.openai_api_key:
                st.error("⚠️ You must enter your OpenAI API Key in the sidebar to use this feature.")
            else:
                hyp_q = st.radio("Select Pre-Launch Hypothesis", ["Q4: The Beloved Figure", "Q6: The Agitator"], index=0)
                with st.form("prelaunch_form"):
                    problem = st.text_area("What exact community problem does your candidacy solve?", height=100)
                    audience = st.text_input("Who is suffering most from this problem?")
                    if st.form_submit_button("Generate Launch Copy"):
                        with st.spinner("Engineering perception..."):
                            st.text_area("Launch Email Copy", value=generate_launch_smokescreen(hyp_q, problem, audience, st.session_state.openai_api_key), height=300)

    with tab_pricing:
        st.header("🧬 Fundraising Elasticity & Budget Optimizer")
        st.markdown("Stop guessing where to spend money. Let your quadrant dictate your financial strategy.")
        
        col_price, col_budget = st.columns(2)
        
        with col_price:
            st.subheader("💰 Fundraising Engine")
            st.caption("Calculates your 'Max Ask' potential based on Viability and Momentum.")
            with st.form("price_form"):
                base_ask = st.number_input("What is your standard 'low-dollar' ask?", min_value=1.0, value=25.00, step=1.0)
                p_pv = st.slider("Your Current PV Score", 0, 100, 50)
                p_momentum = st.slider("Your Current Momentum Score", 0, 100, 20)
                if st.form_submit_button("Calculate Optimal Fundraising"):
                    pricing_data = calculate_pricing_elasticity(p_pv, p_momentum, base_ask)
                    st.metric("Optimal 'High-Dollar' Ask", pricing_data["Optimal 'Max Ask'"])
                    st.info(f"**Strategy:** {pricing_data['Strategy']}")
        with col_budget:
            st.subheader("📊 Budget Allocation Engine")
            st.caption("Tells you exactly what percentage of your budget to allocate to Field, Ads, and Digital based on your quadrant.")
            if st.session_state.latest_quadrant:
                budget_data = calculate_budget_allocation(st.session_state.latest_quadrant, selected_race_type)
                st.metric("Current Quadrant", st.session_state.latest_quadrant.split(":")[0])
                
                df_budget = pd.DataFrame({"Focus Area": list(budget_data.keys()), "% of Budget": list(budget_data.values())})
                fig_budget = px.pie(df_budget, values='% of Budget', names="Focus Area", hole=0.5, title="Recommended Budget Split")
                st.plotly_chart(fig_budget, use_container_width=True)
            else:
                st.info("Assess a campaign in the 'Manual' or 'AI Audit' tab to activate this engine.")

    with tab_team:
        st.header("🤝 Team Alignment Diagnostic")
        st.markdown("**The Silent Killer of Campaigns:** The Candidate and the Campaign Manager often view the race differently. This tool exposes internal friction.")
        
        st.markdown("### Step 1: Quantify the Perspectives")
        
        with st.form("team_form"):
            col_s, col_m = st.columns(2)
            
            with col_s:
                st.markdown("#### 🧑 Candidate Perspective")
                s_vr = st.slider("Candidate: Voter Resonance", 0, 100, 50, key="s_vr")
                s_pv = st.slider("Candidate: Policy Viability", 0, 100, 50, key="s_pv")
                s_pi = st.slider("Candidate: Public Integrity", 0, 100, 50, key="s_pi")
                s_m = st.slider("Candidate: Momentum", 0, 100, 50, key="s_m")
            
            with col_m:
                st.markdown("#### 🎨 Campaign Manager Perspective")
                m_vr = st.slider("Manager: Voter Resonance", 0, 100, 70, key="m_vr")
                m_pv = st.slider("Manager: Policy Viability", 0, 100, 80, key="m_pv")
                m_pi = st.slider("Manager: Public Integrity", 0, 100, 80, key="m_pi")
                m_m = st.slider("Manager: Momentum", 0, 100, 20, key="m_m")

            submitted = st.form_submit_button("🚨 Diagnose Alignment")
            
            if submitted:
                cand_scores = NormalizedScores(s_vr, s_pv, s_pi, s_m)
                mgr_scores = NormalizedScores(m_vr, m_pv, m_pi, m_m)
                
                cand_q, _ = classify_quadrant(cand_scores, st.session_state.custom_thresholds)
                mgr_q, _ = classify_quadrant(mgr_scores, st.session_state.custom_thresholds)
                
                is_aligned = (cand_q == mgr_q)

                st.markdown("---")
                st.subheader("📊 Alignment Analysis Results")
                
                m_col1, m_col2, m_col3 = st.columns([1, 1, 1])
                with m_col1:
                    st.metric("Candidate Quadrant", cand_q.split(":")[0])
                with m_col2:
                    st.metric("Manager Quadrant", mgr_q.split(":")[0])
                with m_col3:
                    if is_aligned:
                        st.metric("Status", "✅ ALIGNED")
                    else:
                        st.metric("Status", "❌ MISALIGNED", delta="Friction Detected", delta_color="inverse")

                c1, c2 = st.columns(2)
                with c1:
                    render_radar_chart(cand_scores, title="Candidate Perception")
                with c2:
                    render_radar_chart(mgr_scores, title="Manager Perception")
                
                if not is_aligned:
                    st.error("### 🚨 Critical Friction Detected")
                    if st.session_state.openai_api_key:
                        if st.button("Generate AI Resolution Plan"):
                            with st.spinner("Analyzing friction..."):
                                st.write(generate_team_action_plan(cand_q, mgr_q, st.session_state.openai_api_key))
                    else:
                        st.warning("Add API Key for AI Resolution Plan.")

    with tab_dashboard:
        st.header("📊 Strategy Command Dashboard")
        if not st.session_state.saved_campaigns:
            st.info("Assess some campaigns using the other tabs to see aggregate analytics here.")
        else:
            col_metrics_1, col_metrics_2 = st.columns(2)
            with col_metrics_1:
                st.metric("Total Campaigns Analyzed", len(st.session_state.saved_campaigns))
            with col_metrics_2:
                q_counts = pd.Series([p["quadrant"] for p in st.session_state.saved_campaigns]).value_counts()
                st.metric("Most Common Quadrant", q_counts.index[0].split(":")[0])
            col_chart_1, col_chart_2 = st.columns(2)
            with col_chart_1:
                dist_data = pd.DataFrame([{"Quadrant": p["quadrant"].split(":")[1].strip()} for p in st.session_state.saved_campaigns])
                dist_counts = dist_data["Quadrant"].value_counts().reset_index()
                dist_counts.columns = ["Zone", "Count"]
                fig_dist = px.pie(dist_counts, values='Count', names='Zone', hole=0.4, title="Portfolio Distribution")
                st.plotly_chart(fig_dist, use_container_width=True)
            with col_chart_2:
                avg_scores = NormalizedScores(
                    sum([p["scores"].voter_resonance for p in st.session_state.saved_campaigns]) / len(st.session_state.saved_campaigns),
                    sum([p["scores"].policy_viability for p in st.session_state.saved_campaigns]) / len(st.session_state.saved_campaigns),
                    sum([p["scores"].public_integrity for p in st.session_state.saved_campaigns]) / len(st.session_state.saved_campaigns),
                    sum([p["scores"].momentum for p in st.session_state.saved_campaigns]) / len(st.session_state.saved_campaigns)
                )
                render_radar_chart(avg_scores, title="Average Portfolio Perception")
            st.subheader("Classified Campaigns Log")
            log_data = [{"Campaign Name": p["name"], "Quadrant": p["quadrant"], "VR": p["scores"].voter_resonance, "PV": p["scores"].policy_viability, "PI": p["scores"].public_integrity, "Momentum": p["scores"].momentum} for p in st.session_state.saved_campaigns]
            st.dataframe(pd.DataFrame(log_data), use_container_width=True, hide_index=True)

    with tab_timeline:
        st.header("📈 Score Momentum Over Time")
        if not st.session_state.score_history:
            st.info("Assess campaigns using the other tabs to start tracking momentum.")
        else:
            track_name = st.selectbox("Select Campaign to Track", list(st.session_state.score_history.keys()))
            render_timeline(track_name)

    with tab_momentum_sim:
        st.header("⚡ Momentum Injection Simulator")
        st.markdown("See how artificially spiking Momentum (via events, endorsements, or crises) shifts your strategic position.")
        if st.session_state.saved_campaigns:
            sel_prod = st.selectbox("Select Campaign", [p["name"] for p in st.session_state.saved_campaigns], key="scar_prod")
            prod_data = next((p for p in st.session_state.saved_campaigns if p["name"] == sel_prod), None)
            base_m = prod_data["scores"].momentum
            
            injected_m = st.slider("Inject Momentum Score", 0, 100, int(base_m), key="scar_inject")
            delta = injected_m - base_m
            
            injected_scores = NormalizedScores(
                prod_data["scores"].voter_resonance,
                prod_data["scores"].policy_viability,
                prod_data["scores"].public_integrity,
                injected_m
            )
            original_q, _ = classify_quadrant(prod_data["scores"], st.session_state.custom_thresholds)
            new_q, _ = classify_quadrant(injected_scores, st.session_state.custom_thresholds)
            
            st.write(f"**Base Momentum:** {base_m} ➡️ **Injected Momentum:** {injected_m} (Delta: +{delta})")
            
            c1, c2 = st.columns(2)
            with c1:
                st.metric("Original Quadrant", original_q.split(":")[0])
            with c2:
                st.metric("New Simulated Quadrant", new_q.split(":")[0])
            
            st.markdown("---")
            if injected_m >= 70 and base_m < 70:
                st.success("🎯 **Threshold Crossed:** You have entered High Momentum. Strategy shifts to GOTV and protecting the lead.")
            elif injected_m < 70 and base_m >= 70:
                st.error("⚠️ **Warning:** Momentum dropped. Risk of looking like a 'sinking ship'. Needs immediate positive press.")
        else: 
            st.info("Assess a campaign first.")

    with tab_tasks:
        st.header("Strategy Execution Tracker")
        with st.form("new_task"):
            new_task = st.text_input("Add a new task")
            task_priority = st.selectbox("Priority", ["High", "Medium", "Low"])
            if st.form_submit_button("Add Task") and new_task:
                st.session_state.tasks.append({"task": new_task, "priority": task_priority, "done": False, "date": datetime.now().strftime("%Y-%m-%d")})
                st.rerun()
        st.subheader("Current Tasks")
        if st.session_state.tasks:
            for i, task in enumerate(st.session_state.tasks):
                col1, col2, col3 = st.columns([0.1, 0.7, 0.2])
                is_done = col1.checkbox("", task["done"], key=f"task_{i}")
                if is_done != task["done"]:
                    st.session_state.tasks[i]["done"] = is_done
                    st.rerun()
                text = task['task'] if not task['done'] else f"~~{task['task']}~~"
                col2.write(f"{text} ({task['priority']})")
                col3.write(task['date'])
        else:
            st.write("No tasks yet.")

    with tab_benchmark:
        st.header("🏆 Opposition Research Benchmarking")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Your Candidate")
            my_vr = st.slider("Your VR", 0, 100, 60, key="b_vr")
            my_pv = st.slider("Your PV", 0, 100, 60, key="b_pv")
            my_pi = st.slider("Your PI", 0, 100, 60, key="b_pi")
            my_m = st.slider("Your Momentum", 0, 100, 60, key="b_m")
        with col2:
            st.subheader("Opponent")
            comp_vr = st.slider("Opp VR", 0, 100, 50, key="c_vr")
            comp_pv = st.slider("Opp PV", 0, 100, 50, key="c_pv")
            comp_pi = st.slider("Opp PI", 0, 100, 50, key="c_pi")
            comp_m = st.slider("Opp Momentum", 0, 100, 50, key="c_m")
        if st.button("Compare"):
            my_scores = NormalizedScores(my_vr, my_pv, my_pi, my_m)
            comp_scores = NormalizedScores(comp_vr, comp_pv, comp_pi, comp_m)
            my_q, _ = classify_quadrant(my_scores, st.session_state.custom_thresholds)
            comp_q, _ = classify_quadrant(comp_scores, st.session_state.custom_thresholds)
            st.write(f"**Your Quadrant:** {my_q}")
            st.write(f"**Opponent Quadrant:** {comp_q}")
            df = pd.DataFrame({"Metric": ["VR", "PV", "PI", "Momentum"], "You": [my_vr, my_pv, my_pi, my_m], "Opponent": [comp_vr, comp_pv, comp_pi, comp_m]})
            df = pd.melt(df, id_vars="Metric", var_name="Candidate", value_name="Score")
            fig = px.bar(df, x="Metric", y="Score", color="Candidate", barmode="group")
            st.plotly_chart(fig)
            st.markdown("---")
            st.subheader("⚔️ AI Opposition Attack Strategy")
            if not st.session_state.openai_api_key:
                st.warning("Add your OpenAI API key to generate a strategy.")
            else:
                with st.spinner("Developing attack plan..."):
                    st.write(generate_competitive_counter_strategy(my_q, comp_q, selected_race_type, st.session_state.openai_api_key))

    with tab_reports:
        st.header("Reports & Exports")
        if not st.session_state.saved_campaigns:
            st.warning("No campaigns saved yet.")
        else:
            st.subheader("Saved Campaigns")
            for i, prod in enumerate(st.session_state.saved_campaigns):
                with st.expander(f"{prod['name']} - {prod['quadrant']}"):
                    st.write(f"**Scores:** VR: {prod['scores'].voter_resonance} | PV: {prod['scores'].policy_viability} | PI: {prod['scores'].public_integrity}")
                    if st.button(f"Download PDF for {prod['name']}", key=f"dl_{prod['name']}"):
                        try:
                            pdf_file = generate_pdf_report(prod, st.session_state.custom_thresholds)
                            st.download_button("Download", data=pdf_file, file_name=f"{prod['name']}_report.pdf")
                        except Exception as e:
                            st.error(f"PDF Error: {e}")

if __name__ == "__main__":
    main()
