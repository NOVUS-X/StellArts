export interface DisputeEvidence {
  sow_content: string;
  before_photo_url: string;
  after_photo_url: string;
  chat_logs: { role: "client" | "artisan"; message: string; timestamp: string }[];
}

export interface DisputeItem {
  id: string;
  booking_id: string;
  client_name: string;
  artisan_name: string;
  amount: number;
  status: "pending" | "resolved_client" | "resolved_artisan";
  fairness_score: number;
  confidence_score: number;
  created_at: string;
  evidence: DisputeEvidence;
}

export const mockDisputes: DisputeItem[] = [
  {
    id: "dis-101",
    booking_id: "book-001",
    client_name: "Alice Smith",
    artisan_name: "Bob Builder",
    amount: 500,
    status: "pending",
    fairness_score: 0.85,
    confidence_score: 0.92,
    created_at: "2026-03-24T10:00:00Z",
    evidence: {
      sow_content: "Refurbish the wooden deck in the backyard. Sanding, staining, and repairing 3 loose planks.",
      before_photo_url: "https://images.unsplash.com/photo-1590422402127-99db72202271?w=800&q=80",
      after_photo_url: "https://images.unsplash.com/photo-1591825381766-9285fb278855?w=800&q=80",
      chat_logs: [
        { role: "client", message: "Hi Bob, are you still on track for Friday?", timestamp: "2026-03-23T14:30:00Z" },
        { role: "artisan", message: "Yes, just finishing up the sanding now. Should be ready for staining tomorrow.", timestamp: "2026-03-23T15:00:00Z" },
        { role: "client", message: "Great! Please make sure to fix those loose planks near the door.", timestamp: "2026-03-24T09:00:00Z" },
        { role: "artisan", message: "All done! Fixed the planks and finished the staining.", timestamp: "2026-03-24T12:00:00Z" },
      ]
    }
  },
  {
    id: "dis-102",
    booking_id: "book-002",
    client_name: "Charlie Brown",
    artisan_name: "Dana Designer",
    amount: 1200,
    status: "pending",
    fairness_score: 0.45,
    confidence_score: 0.35,
    created_at: "2026-03-25T14:00:00Z",
    evidence: {
      sow_content: "Complete UI design for a mobile app including 10 screens and a design system.",
      before_photo_url: "https://images.unsplash.com/photo-1586717791821-3f44a563de4c?w=800&q=80", // Sketch
      after_photo_url: "https://images.unsplash.com/photo-1581291417084-21971775cf04?w=800&q=80", // Incomplete design
      chat_logs: [
        { role: "client", message: "Wait, this only looks like 4 screens. We agreed on 10.", timestamp: "2026-03-25T10:00:00Z" },
        { role: "artisan", message: "I'm still working on the rest. I need more time.", timestamp: "2026-03-25T11:00:00Z" },
        { role: "client", message: "The deadline was today. I'm raising a flag because the work is clearly incomplete.", timestamp: "2026-03-25T13:30:00Z" }
      ]
    }
  }
];
