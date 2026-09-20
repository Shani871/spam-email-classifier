"""
Dataset preparation script for Spam Email Classifier.
Downloads standard spam benchmark dataset and augments it with realistic modern email samples
(phishing lures, corporate messages, transactional alerts, marketing promos).
Saves the cleaned, consolidated dataset to dataset/spam.csv.
"""

import os
import urllib.request
import pandas as pd

DATASET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dataset")
OUTPUT_CSV = os.path.join(DATASET_DIR, "spam.csv")
RAW_DATA_URL = "https://raw.githubusercontent.com/justmarkham/DAT8/master/data/sms.tsv"

# Additional modern email samples for ham and spam to ensure high-fidelity classification of email bodies
MODERN_EMAIL_SAMPLES = [
    # Modern Ham Emails
    ("ham", "Subject: Team Sync Agenda - Monday 10:00 AM\nHi all, please find the agenda for our upcoming sprint planning meeting attached. Let me know if you have any points to add before Monday."),
    ("ham", "Subject: Invoice Payment Confirmation #48291\nDear Customer, your recent payment of $120.50 for Cloud Services has been successfully processed. The receipt is attached for your accounting records."),
    ("ham", "Subject: Project Milestone Review - Antigravity IDE\nHey Alex, I have updated the pull request with your suggested fixes for the memory leak. Could you please take another look and approve when ready?"),
    ("ham", "Subject: Dental Appointment Reminder\nHi Shani, this is a reminder for your dental checkup scheduled for Thursday, October 15 at 2:30 PM. Please reply CONFIRM or call our clinic if you need to reschedule."),
    ("ham", "Subject: Quarterly Financial Summary Report\nHello Management Team, attached is the Q3 performance report including revenue breakdown and operating expenses. We will discuss key takeaways in the town hall."),
    ("ham", "Subject: Your order #938102 has shipped!\nGreat news! Your package from Amazon is on the way and scheduled to arrive by Wednesday. Track your package anytime via the order details page in your account."),
    ("ham", "Subject: Notes from today's design discussion\nThanks everyone for joining today's session. Key action items: 1. Finalize wireframes by Wednesday. 2. Share feedback with the frontend team. Let me know if I missed anything."),
    ("ham", "Subject: Code review requested: Feature/auth-flow\nHello, could you please review the OAuth2 implementation on branch feature/auth-flow? All unit and integration tests are currently passing."),
    ("ham", "Subject: Flight itinerary: SFO to JFK\nYour booking confirmation code is W7K9PL. Departure is scheduled for November 12 at 8:45 AM. Terminal 2, Gate B14. Please check in 24 hours prior to departure."),
    ("ham", "Subject: Welcome to the Engineering Team!\nWelcome aboard! We are thrilled to have you join our team. Your onboarding buddy will reach out shortly to guide you through system setup and team channels."),

    # Modern Spam / Phishing Emails
    ("spam", "Subject: URGENT: Your PayPal Account Has Been Suspended!\nDear user, suspicious login attempts were detected from an unknown IP address. To avoid permanent account closure, click here immediately to verify your identity and update your billing credentials: http://secure-paypal-verify-account-now.com"),
    ("spam", "URGENT: Your PayPal account is locked. Verify bank credentials immediately to avoid suspension. Click to reactivate now."),
    ("spam", "Security Notice: Suspicious sign-in detected on your bank account. Verify your login credentials and personal identity immediately or access will be terminated."),
    ("spam", "Congratulations! You Have Been Selected for a $5,000 Walmart Gift Card\nYou have been chosen as today's grand prize winner in our annual rewards sweepstakes. Claim your free $5,000 gift card now by completing a quick 2-minute survey. Offer expires in 24 hours!"),
    ("spam", "FINAL NOTICE: Outstanding Tax Debt of $4,980.00\nInternal Revenue Service Notice: You have an unpaid balance subject to immediate legal action and asset forfeiture. Call our direct hotline immediately or transfer settlement payment to avoid arrest."),
    ("spam", "Work From Home & Earn $500-$1500 Daily Guaranteed!\nNo experience required! Flexible hours, work 1-2 hours a day from your phone or laptop. Immediate payouts directly to your bank or Bitcoin wallet. Reply YES or click the link to start today."),
    ("spam", "INVOICE OVERDUE: Click to download wire transfer instructions\nAttached is invoice INV-9021 for the overdue software license payment. Please wire $3,450 to the account details provided in the attached macro-enabled document immediately."),
    ("spam", "You inherited 12.5 Million USD from late Dr. John Edwards\nI am barrister Richard Vance, personal attorney to the deceased. He left no next of kin and nominated you as beneficiary to claim his estate. Reply with your passport and bank coordinates to begin transfer."),
    ("spam", "Exclusive Prescription Offer: 80% OFF All Medications Today Only!\nBuy genuine Viagra, Cialis, and weight loss remedies without prescription! Free worldwide express shipping on all orders over $50. Click here to browse our discreet pharmacy catalog."),
    ("spam", "Security Alert: Unauthorized wire transfer initiated from your Chase Bank account\nA transfer of $2,400.00 to an overseas account was initiated. If you did not authorize this transaction, click Cancel Transaction immediately to block the funds: http://chase-security-fraud-alert.ru/cancel"),
    ("spam", "Hot singles in your area want to chat tonight!\n3 new attractive members near your location viewed your profile and sent you private messages. Click here to see who likes you and start instant video chat for free!"),
    ("spam", "Double your Crypto in 48 hours! 200% ROI guaranteed\nJoin our VIP automated crypto trading bot. Deposit 0.1 BTC today and receive 0.3 BTC back guaranteed in 2 days. 100% risk-free algorithmic arbitrage trading!"),
    ("spam", "Important notification: You have won lottery cash reward! Call now or text CLAIM to 88442 to receive your payout.")
]

def prepare_dataset():
    os.makedirs(DATASET_DIR, exist_ok=True)
    print(f"Fetching base dataset from {RAW_DATA_URL}...")
    
    try:
        req = urllib.request.Request(RAW_DATA_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            content = response.read().decode('utf-8', errors='ignore')
        
        lines = [line for line in content.strip().split('\n') if line]
        records = []
        for line in lines:
            parts = line.split('\t', 1)
            if len(parts) == 2:
                label = parts[0].strip().lower()
                text = parts[1].strip()
                if label in ['ham', 'spam'] and text:
                    records.append((label, text))
        
        df_base = pd.DataFrame(records, columns=['label', 'text'])
        print(f"Loaded {len(df_base)} base records from remote source.")
    except Exception as e:
        print(f"Remote fetch failed ({e}). Falling back to internal seed dataset.")
        records = [
            ("ham", "Are you coming to the office today? Let me know when you arrive."),
            ("ham", "Sounds good, see you at lunch!"),
            ("ham", "Can you send me the slides for the presentation?"),
            ("spam", "Win a guaranteed $1000 cash prize! Text WIN to 55432 to claim right now."),
            ("spam", "URGENT: Your credit card has been compromised. Call 1-800-FAKE-NUM immediately."),
            ("spam", "Congratulations! You won a brand new iPhone 15 Pro. Click here to receive it free.")
        ]
        df_base = pd.DataFrame(records, columns=['label', 'text'])
    
    # Add modern email samples
    df_modern = pd.DataFrame(MODERN_EMAIL_SAMPLES, columns=['label', 'text'])
    df_combined = pd.concat([df_base, df_modern], ignore_index=True)
    
    # Drop duplicates and clean formatting
    df_combined = df_combined.drop_duplicates(subset=['text']).reset_index(drop=True)
    df_combined['label'] = df_combined['label'].str.lower().str.strip()
    
    # Save to CSV
    df_combined.to_csv(OUTPUT_CSV, index=False)
    print(f"Dataset successfully created at: {OUTPUT_CSV}")
    print(f"Total rows: {len(df_combined)}")
    print("Class distribution:")
    print(df_combined['label'].value_counts())

if __name__ == "__main__":
    prepare_dataset()
