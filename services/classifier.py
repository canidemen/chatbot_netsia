from transformers import pipeline
import time

CONFIDENCE_THRESHOLD = 0.7      #if lower, kafka
classifier = pipeline("zero-shot-classification", model="MoritzLaurer/deberta-v3-large-zeroshot-v2.0")

LABELS = [
    {
        "id": "billing",
        "name": "Billing Issue",
        "description": "Charges, invoices, overbilling, refunds, payment failures.",
        "synonyms": ["bill", "charge", "invoice", "payment", "refund", "credit card"]
    },
    {
        "id": "connectivity",
        "name": "Internet Connectivity",
        "description": "No connection, slow speeds, intermittent drops, latency.",
        "synonyms": ["no internet", "offline", "slow", "lag", "disconnect", "packet loss"]
    },
    {
        "id": "device_config",
        "name": "Device Configuration",
        "description": "Router/modem setup, firmware, Wi‑Fi password, port forwarding.",
        "synonyms": ["router", "modem", "firmware", "wifi password", "port forward", "ssid"]
    },
    {
        "id": "cancellation",
        "name": "Cancellation",
        "description": "Cancel service, downgrade, upgrade, pause account.",
        "synonyms": ["cancel", "terminate", "end service", "stop plan", "downgrade", "upgrade"]
    },
    {
        "id": "general_info",
        "name": "General Information",
        "description": "Pricing plans, coverage, availability, sales questions.",
        "synonyms": ["price", "plan", "available", "coverage", "offer", "promotion"]
    },
    {
        "id": "chitchat",
        "name": "ChitChat",
        "description": "Greetings, thanks, casual conversation not needing action.",
        "synonyms": ["hi", "hello", "thanks", "how are you", "good morning"]
    }
]


def classify(message):
    start = time.perf_counter()

    
    result = classifier(
        message,
        candidate_labels = [f"{lbl['name']}: {lbl['description']}" for lbl in LABELS]
    )

    confidence = result["scores"][0]
    label = result["labels"][0]

    print(result)

    total = time.perf_counter() - start
    print(f"Total classification duration: {total:.2f} seconds")


    return (label, confidence) if confidence > CONFIDENCE_THRESHOLD else (None, None)


