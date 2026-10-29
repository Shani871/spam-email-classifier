"""Multilingual localization and terminology consistency for SpamGuard AI.

Provides consistent Hindi, Hinglish, and English terminology with an English fallback.
Explains recovery steps and honest language coverage limitations.
"""

from typing import Dict, List, Any

# Standardized terminology for risk assessments
ASSESSMENT_LABELS: Dict[str, Dict[str, str]] = {
    "English": {
        "High risk": "High risk",
        "Needs verification": "Needs verification",
        "No strong warning found": "No strong warning found",
        "Unable to assess": "Unable to assess",
    },
    "Hindi": {
        "High risk": "उच्च जोखिम (High Risk)",
        "Needs verification": "पुष्टि आवश्यक (Needs Verification)",
        "No strong warning found": "कोई बड़ा चेतावनी संकेत नहीं (No Strong Warning)",
        "Unable to assess": "जाँच के लिए अपर्याप्त जानकारी (Unable to Assess)",
    },
    "Hinglish": {
        "High risk": "Zyada Risk (High Risk)",
        "Needs verification": "Pehle Verify Karein (Needs Verification)",
        "No strong warning found": "Koi Strong Warning Nahi (No Strong Warning)",
        "Unable to assess": "Check Karne Ke Liye Details Kam Hain (Unable to Assess)",
    },
}

# Standardized assessment summaries
ASSESSMENT_SUMMARIES: Dict[str, Dict[str, str]] = {
    "English": {
        "High risk": "Several warning indicators were found. Pause before paying, clicking, or sharing information.",
        "Needs verification": "Verify this request independently before taking a sensitive action.",
        "No strong warning found": "These checks found no strong warning. The sender and request are not verified.",
        "Unable to assess": "There is too little useful content for a reliable assessment.",
    },
    "Hindi": {
        "High risk": "संदेश में कई गंभीर चेतावनी संकेत मिले हैं। पैसे भेजने, लिंक खोलने या जानकारी साझा करने से पहले रुकें।",
        "Needs verification": "कोई भी संवेदनशील कदम उठाने से पहले स्वतंत्र रूप से इस अनुरोध की पुष्टि करें।",
        "No strong warning found": "इस जांच में कोई बड़ा खतरा नहीं दिखा, लेकिन प्रेषक की प्रामाणिकता सत्यापित नहीं है। सतर्क रहें।",
        "Unable to assess": "सटीक मूल्यांकन के लिए संदेश में पर्याप्त सामग्री नहीं है।",
    },
    "Hinglish": {
        "High risk": "Message mein kayi risk indicators mile hain. Paise transfer karne ya link kholne se pehle ruk jayein.",
        "Needs verification": "Koi bhi sensitive action lene se pehle is request ko independently verify karein.",
        "No strong warning found": "In checks mein koi strong warning nahi mili, lekin sender verify nahi hua hai. Satark rahein.",
        "Unable to assess": "Sahi check karne ke liye message mein kaafi content nahi hai.",
    },
}

# Evidence title and advice translations
EVIDENCE_LOCALIZATIONS: Dict[str, Dict[str, Dict[str, str]]] = {
    "Recruitment payment requested": {
        "Hindi": {
            "title": "भर्ती या नौकरी के लिए भुगतान की मांग",
            "advice": "भुगतान करने से पहले नियोक्ता की आधिकारिक वेबसाइट या करियर पोर्टल से नौकरी की पुष्टि करें। कोई वैध कंपनी भर्ती के लिए पैसे नहीं मांगती।"
        },
        "Hinglish": {
            "title": "Job ya internship ke liye fees maangi gayi",
            "advice": "Payment karne se pehle employer ke official careers page se vacancy check karein. Genuine companies kabhi registration fees nahi leti."
        }
    },
    "Equipment payment or fake-check pattern": {
        "Hindi": {
            "title": "उपकरण या चेक भुगतान का संदिग्ध पैटर्न",
            "advice": "कार्यालय उपकरण व्यवस्था की स्वतंत्र रूप से पुष्टि करें; किसी अज्ञात चेक से पैसे आगे ट्रांसफर न करें।"
        },
        "Hinglish": {
            "title": "Equipment ya cheque payment ka suspicious pattern",
            "advice": "Equipment arrangements ki independent confirmation karein; kisi unfamiliar cheque se paise aage transfer na karein."
        }
    },
    "Sensitive information requested": {
        "Hindi": {
            "title": "गोपनीय जानकारी (ओटीपी/पासवर्ड/पहचान पत्र) की मांग",
            "advice": "दस्तावेज़ साझा करने से पहले प्रेषक और उद्देश्य की पुष्टि करें। कभी भी किसी के साथ पासवर्ड या ओटीपी साझा न करें।"
        },
        "Hinglish": {
            "title": "Sensitive jaankari (OTP/Password/ID) share karne ko kaha gaya",
            "advice": "Documents share karne se pehle recipient aur purpose verify karein. Kabhi bhi OTP ya passwords share na karein."
        }
    },
    "Pay-to-withdraw task scheme": {
        "Hindi": {
            "title": "कमाई निकालने के लिए शुल्क जमा करने की धोखाधड़ी",
            "advice": "कमीशन निकालने के लिए पहले पैसे जमा करने की किसी भी मांग पर तुरंत रुकें और स्वतंत्र जांच करें।"
        },
        "Hinglish": {
            "title": "Task earnings withdraw karne ke liye deposit maangna",
            "advice": "Earnings withdraw karne ke liye paise mangne wale offers fraud hote hain. Turant ruk jayein."
        }
    },
    "Payment details differ from the earlier message": {
        "Hindi": {
            "title": "पिछले संदेश से भुगतान विवरण में अंतर",
            "advice": "भुगतान करने से पहले विक्रेता से उनके पहले से ज्ञात सत्यापित फोन नंबर पर बात करें। केवल बदलाव धोखाधड़ी का प्रमाण नहीं है।"
        },
        "Hinglish": {
            "title": "Pichhle message se payment details badal gaye hain",
            "advice": "Payment karne se pehle supplier ko unke pehle se trusted phone number par call karein. Badlaav apne aap mein fraud ka pakka saboot nahi hai."
        }
    },
    "Sender email domain changed": {
        "Hindi": {
            "title": "भेजने वाले का ईमेल डोमेन बदल गया है",
            "advice": "इस संदेश से पहले मौजूद संपर्क माध्यम से अपने सहयोगी या कंपनी से पुष्टि करें। मिलते-जुलते डोमेन अक्सर धोखाधड़ी में उपयोग किए जाते हैं।"
        },
        "Hinglish": {
            "title": "Sender ka email domain change ho gaya hai",
            "advice": "Apne partner se purane trusted phone number ya channel se confirm karein. Lookalike domains aksar fraud ke liye use hote hain."
        }
    },
    "Reply-To address changed from earlier messages": {
        "Hindi": {
            "title": "उत्तर देने का पता (Reply-To) बदल गया है",
            "advice": "उत्तर भेजने से पहले प्राप्तकर्ता का पता ध्यान से जांचें ताकि संदेश किसी अनपेक्षित पते पर न जाए।"
        },
        "Hinglish": {
            "title": "Reply-To address pichhle message se badal gaya hai",
            "advice": "Reply button dabane se pehle to-address check karein taaki message galat email par na jaye."
        }
    },
    "Sender is on your blocked list": {
        "Hindi": {
            "title": "प्रेषक आपकी ब्लॉक सूची में है",
            "advice": "उत्तर देने से पहले इस संदेश की स्वतंत्र रूप से पुष्टि करें।"
        },
        "Hinglish": {
            "title": "Sender aapki blocked list mein hai",
            "advice": "Reply karne se pehle is message ko independently verify karein."
        }
    },
    "Utility disconnection threat / fake electricity bill": {
        "Hindi": {
            "title": "बिजली/यूटिलिटी कनेक्शन काटने की धमकी या फर्जी बिल",
            "advice": "बिजली विभाग कुछ ही घंटों में संदेश भेजकर कनेक्शन काटने या व्यक्तिगत नंबर पर कॉल करके बिल भरने को नहीं कहता। आधिकारिक डिस्कॉम पोर्टल या ऐप पर बिल की जांच करें।"
        },
        "Hinglish": {
            "title": "Bijli connection cut karne ki threat ya fake utility bill",
            "advice": "Electricity department message bhej kar turant connection kaatne ya personal number par call karke bill bharne ko nahi kehta. Official utility website ya app par bill verify karein."
        }
    },
    "New payment details introduced in conversation": {
        "Hindi": {
            "title": "बातचीत में नया भुगतान विवरण पेश किया गया",
            "advice": "पिछले ज्ञात फोन नंबर का उपयोग करके विक्रेता से सीधे बात करें। बातचीत के दौरान नए खाते या यूपीआई आईडी जोड़ना सत्यापन की मांग करता है।"
        },
        "Hinglish": {
            "title": "Conversation mein new payment details add kiye gaye",
            "advice": "Pehle se trusted phone number par call karke supplier se confirm karein. Mid-thread new accounts verify karna zaroori hai."
        }
    },
    "New external links introduced in conversation": {
        "Hindi": {
            "title": "बातचीत में नए बाहरी लिंक जोड़े गए",
            "advice": "किसी भी बाहरी लिंक पर क्लिक करने से पहले पुष्टि करें। क्रेडेंशियल दर्ज करने से पहले डोमेन नाम को ध्यान से देखें।"
        },
        "Hinglish": {
            "title": "Conversation mein new external links introduce huye",
            "advice": "Kisi bhi external link par click karne se pehle confirm karein. Credentials enter karne se pehle domain check karein."
        }
    },
    "Sensitive information request escalated in conversation": {
        "Hindi": {
            "title": "बातचीत में गोपनीय जानकारी की मांग बढ़ गई",
            "advice": "पासवर्ड, ओटीपी या पहचान पत्र कभी साझा न करें। प्रेषक के इरादे और पहचान की पुष्टि करें।"
        },
        "Hinglish": {
            "title": "Conversation mein sensitive info request escalate hui",
            "advice": "Passwords, OTP ya ID documents kabhi share na karein. Sender ki identity pehle verify karein."
        }
    },
    "Link destination changed within the same domain": {
        "Hindi": {
            "title": "समान डोमेन के भीतर लिंक का गंतव्य बदल गया है",
            "advice": "वैध लिंक भी अपडेट हो सकते हैं, लेकिन संवेदनशील जानकारी दर्ज करने से पहले नए पृष्ठ की पुष्टि करें।"
        },
        "Hinglish": {
            "title": "Same domain ke andar link destination change hua",
            "advice": "Legitimate links bhi change ho sakte hain, par sensitive information enter karne se pehle new page verify karein."
        }
    }
}

# Detailed recovery steps across all situation stages
RECOVERY_GUIDES: Dict[str, Dict[str, List[str]]] = {
    "English": {
        "Only received the message": [
            "Pause before replying, paying, or opening any links or attachments.",
            "Verify the request using an official website or a contact number you already trusted before this message.",
            "Preserve a copy or screenshot of the message in case you need to report it.",
            "Do not engage with the sender or confront them."
        ],
        "Clicked a link": [
            "Close the browser tab immediately and avoid downloading any files or accepting certificate warnings.",
            "If you entered credentials, immediately open the official website in a fresh tab and change your password.",
            "Run a full anti-malware scan on your computer or mobile device.",
            "Review your browser's recent downloads folder and delete any unfamiliar downloaded files."
        ],
        "Shared a password or OTP": [
            "Immediately sign in to the legitimate service from an official app and change the compromised password.",
            "Sign out of all other active sessions and revoke unknown device access.",
            "If a banking or payment credential was shared, call your bank's fraud emergency hotline right away to freeze cards/accounts.",
            "Enable multi-factor authentication (MFA) using an authenticator app rather than SMS where possible."
        ],
        "Sent money or payment details": [
            "Contact your bank or payment provider immediately (via their official emergency number) to request a recall or stop-payment.",
            "In India, file a complaint on the National Cyber Crime Portal (https://cybercrime.gov.in) or call helpline 1930.",
            "Preserve all transaction receipts, UTR numbers, UPI IDs, and chat records as evidence.",
            "Beware of 'recovery scam' services on social media claiming they can recover lost funds for an upfront fee."
        ]
    },
    "Hindi": {
        "Only received the message": [
            "जवाब देने, भुगतान करने या किसी भी लिंक पर क्लिक करने से पहले रुकें।",
            "इस संदेश से पहले मौजूद किसी आधिकारिक नंबर या वेबसाइट से संपर्क करके पुष्टि करें।",
            "संदेश का स्क्रीनशॉट या प्रति सुरक्षित रखें ताकि आवश्यकता पड़ने पर शिकायत दर्ज कर सकें।",
            "प्रेषक से बहस न करें और न ही कोई अतिरिक्त जानकारी साझा करें।"
        ],
        "Clicked a link": [
            "तुरंत ब्राउज़र टैब बंद करें और किसी भी फाइल को डाउनलोड या अनुमति न दें।",
            "यदि आपने पासवर्ड या कोई विवरण दर्ज किया था, तो आधिकारिक ऐप पर जाकर तुरंत अपना पासवर्ड बदलें।",
            "अपने डिवाइस की सुरक्षा सेटिंग्स जांचें और एंटी-वायरस स्कैन चलाएं।",
            "डाउनलोड फ़ोल्डर में जाकर किसी भी अनजान फाइल को तुरंत हटा दें।"
        ],
        "Shared a password or OTP": [
            "तुरंत आधिकारिक ऐप या वेबसाइट पर जाकर प्रभावित खाते का पासवर्ड बदलें।",
            "सभी अन्य डिवाइस से लॉग-आउट (Sign out all sessions) करें और रिकवरी ईमेल/नंबर जांचें।",
            "यदि बैंक या यूपीआई का विवरण साझा हुआ है, तो तुरंत अपने बैंक के हेल्पलाइन नंबर पर कॉल करके कार्ड या खाता ब्लॉक कराएं।",
            "एसएमएस के बजाय ऑथेंटिकेटर ऐप से 2-स्टेप वेरिफिकेशन चालू करें।"
        ],
        "Sent money or payment details": [
            "तुरंत अपने बैंक या पेमेंट ऐप (GPay/PhonePe/Paytm) के आधिकारिक आपातकालीन नंबर पर कॉल करके ट्रांजेक्शन रोकने का अनुरोध करें।",
            "भारत में तुरंत साइबर हेल्पलाइन 1930 पर कॉल करें या https://cybercrime.gov.in पर शिकायत दर्ज करें।",
            "सभी लेन-देन रसीदें, यूटीआर (UTR) नंबर, यूपीआई आईडी और चैट स्क्रीनशॉट सुरक्षित रखें।",
            "सोशल मीडिया पर पैसे वापस दिलाने का दावा करने वाले फर्जी रिकवरी एजेंटों से सावधान रहें।"
        ]
    },
    "Hinglish": {
        "Only received the message": [
            "Reply karne, paise transfer karne ya link kholne se pehle pause karein.",
            "Message ko verify karne ke liye unka pehle se trusted contact number ya official website use karein.",
            "Message ka screenshot ya copy save karke rakhein future reporting ke liye.",
            "Sender se interact na karein aur na hi unhe alert karein."
        ],
        "Clicked a link": [
            "Browser tab turant band karein aur koi bhi file download na hone dein.",
            "Agar password ya details daal di hain, to official app par jakar turant password change karein.",
            "Apne phone ya computer mein antivirus/security scan run karein.",
            "Downloads folder check karein aur koi bhi unknown file delete karein."
        ],
        "Shared a password or OTP": [
            "Official app par login karke turant password badlein aur active sessions sign-out karein.",
            "Agar banking details ya UPI PIN share kiya hai, to turant bank helpline par call karke card/account block karwayein.",
            "Apne email aur banking accounts par Two-Factor Authentication (2FA) activate karein.",
            "Bank ke official statement mein suspicious transactions monitor karein."
        ],
        "Sent money or payment details": [
            "Turant apne bank ya payment service ke official emergency number par call karein aur transaction reverse/freeze karne ko kahein.",
            "India mein national cyber helpline 1930 par call karein ya https://cybercrime.gov.in par complaint darj karein.",
            "Saare payment receipts, UTR number, UPI reference aur chat screenshots evidence ke roop mein preserve karein.",
            "Paise wapas dilane ka claim karne wale fake 'recovery agents' se door rahein; ye doosra fraud hota hai."
        ]
    }
}


def localize_evidence_item(evidence_item: Dict[str, Any], language: str = "English") -> Dict[str, Any]:
    """Translates title and advice for an evidence item, falling back to English."""
    if language == "English":
        return evidence_item

    title = evidence_item.get("title", "")
    trans = EVIDENCE_LOCALIZATIONS.get(title, {}).get(language)
    if trans:
        localized = dict(evidence_item)
        localized["title"] = trans.get("title", title)
        localized["advice"] = trans.get("advice", evidence_item.get("advice", ""))
        return localized

    return evidence_item


def get_localized_recovery_steps(stage: str, language: str = "English") -> List[str]:
    """Returns comprehensive recovery steps for the given stage and language."""
    lang_dict = RECOVERY_GUIDES.get(language, RECOVERY_GUIDES["English"])
    return lang_dict.get(stage, RECOVERY_GUIDES["English"].get(stage, []))


def get_language_limitations(language: str) -> List[str]:
    """Returns honest coverage limitations for the selected language."""
    if language == "Hindi":
        return [
            "हिंदी संदेशों की जांच नियम-आधारित पैटर्न पर आधारित है। अंग्रेज़ी मशीन लर्निंग मॉडल का स्कोर हिंदी पर विश्वसनीय नहीं माना जाना चाहिए।",
            "संकेत केवल संदिग्ध पैटर्न दर्शाते हैं; यह किसी संदेश के शत-प्रतिशत सुरक्षित होने का प्रमाण नहीं है।",
            "ईमेल अटैचमेंट की केवल मेटाडेटा और नाम से जांच होती है, मैलवेयर स्कैनिंग नहीं।"
        ]
    elif language == "Hinglish":
        return [
            "Hinglish detection keyword rules aur threat cues par depend karti hai. English ML model confidence Hinglish text ke liye calibrated nahi hai.",
            "Warning ka na hona safety ka absolute proof nahi hai; hamesha independent verification karein.",
            "Attachments ki checking sirf filename aur metadata par hoti hai; antivirus file scanning nahi hoti."
        ]
    return [
        "Risk indicators do not establish authenticity. Absence of a warning does not prove safety.",
        "The spam model was evaluated on an English benchmark, not all modern scam types.",
        "Attachments are checked by metadata only; file contents are not scanned for malware."
    ]
