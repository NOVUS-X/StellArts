# StellArts Frontend

This is the fully responsive and authenticated Next.js frontend application for the **StellArts Platform**, integrating advanced functionality like Role-based Dashboard Access, JWT Authentication, and a Stellar testnet-powered Smart Contract Escrow System for booking payments.

## 🚀 Features & Architecture

- **Next.js 14 App Router**: Utilizes the modern React architecture for layout structures, nested routes, and optimal rendering.
- **Role-Aware Dashboard (/dashboard)**: 
  - Authenticated layout strictly routes users based on JWT validity. 
  - Distinguishes visually and functionally between `client` and `artisan` accounts.
- **Booking Management (/dashboard/bookings)**:
  - Supports colorful status badges.
  - Granular interactive filter tabs (`All`, `Pending`, `Active`, `Completed`).
  - Optimistic UI updates ensure instantaneous user feedback when changing a booking status before the backend fully syncs.
- **Stellar Escrow Payment Flow (/dashboard/payments)**:
  - Features a seamless Freighter Wallet integration via `@creit.tech/stellar-wallets-kit`.
  - Full automated payment modal workflow: `Prepare XDR` → `Sign locally via Wallet UI` → `Submit Signed Transaction to Backend` → `Link to Stellar Explorer`.
- **UI & UX System (`Stellar Midnight`)**: Built completely with Tailwind CSS, `radix-ui`, `lucide-react` icons, and standard modular components (Card, Dialog, Navbar). Elements are crafted to be fully-width, airy, and dynamically responsive across all viewport sizes.

## 🛠️ Setup & Local Development

1. **Install dependencies**:
   ```bash
   npm install
   ```
2. **Setup environment variables** (`.env.local`):
   Ensure your `.env.local` points to your backend instance:
   ```bash
   NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
   ```
3. **Run the development server**:
   ```bash
   npm run dev
   ```
   *The app uses Tailwind for live-reloading UI styling. The site will be available on `http://localhost:3000`.*

---

## 🎨 Design Philosophy (`Stellar Midnight`)

The design does not constrain heroes or component layouts aggressively to the center. Instead, components dynamically populate across the full width of the view boundaries on desktops and intelligently wrap and stack natively on mobile devices.
Styling leverages slate blues, midnight undertones, amber warnings (for pending actions), and emerald successes (for confirmations or active flows) to seamlessly inform the user about the application state intuitively.

## 🧪 Validations
- `npm run lint`: Enforces ESLint standards across all TS/TSX contexts.
- `npm run typecheck`: Validates all TypeScript types using strict rules avoiding runtime exceptions.
