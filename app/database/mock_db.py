# app/database/mock_db.py

ABUELITOS_DB = {
    "Don Manuel": {
        "demographics": {
            "age": 72,
            "city": "Ecatepec, EDOMEX",
            "living_situation": "Lives Alone"
        },
        "caregiver_routing": {
            "son_name": "Guillermo Pineda",
            "caregiver_phone": "+525512345678"
        },
        "medical_baseline": {
            "critical_medication": "Losartán 50mg (Blood Pressure)",
            "expected_intake_window": "08:00 AM - 09:30 AM"
        },
        "learned_behavioral_baselines": {
            "avg_waking_hour": 8.0,          # Learns normal morning wake-up time
            "avg_word_count": 12.0,          # Learns normal talking message length
            "total_logs_count": 0
        },
        "anomaly_thresholds": {
            "max_allowed_delay_hours": 2.5,  # Alert if 2.5 hours past typical time
            "speech_drop_percentage": 0.40   # Alert if speech drops below 40% of standard volume
        }
    }
}

