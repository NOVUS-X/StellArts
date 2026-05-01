# StellArts Design System

This directory contains standardized UI components for the StellArts frontend application.

## Overview

The design system is built on:
- **Tailwind CSS v4** - Utility-first CSS framework
- **class-variance-authority (CVA)** - Component variant management
- **Radix UI** - Headless UI primitives
- **Lucide React** - Icon library

## Component Index

### Core Components

| Component | Description | Status |
|-----------|-------------|--------|
| [Button](./button.tsx) | Interactive button with variants | ✅ Existing |
| [Card](./card.tsx) | Content container with header/footer | ✅ Existing |
| [Input](./input.tsx) | Form input field | ✅ New |
| [Textarea](./textarea.tsx) | Multi-line text input | ✅ New |
| [Label](./label.tsx) | Form field label | ✅ New |
| [Badge](./badge.tsx) | Status indicators and tags | ✅ New |
| [Alert](./alert.tsx) | Notification messages | ✅ New |
| [Dialog](./dialog.tsx) | Modal dialog windows | ✅ New |

### Additional Components

| Component | Description | Status |
|-----------|-------------|--------|
| [CurrencySelector](./CurrencySelector.tsx) | Currency selection dropdown | ✅ Existing |
| [Footer](./Footer.tsx) | Page footer | ✅ Existing |
| [Navbar](./Navbar.tsx) | Navigation bar | ✅ Existing |
| [NotificationBell](./NotificationBell.tsx) | Notification indicator | ✅ Existing |
| [Price](./Price.tsx) | Price display | ✅ Existing |
| [StarRating](./star-rating.tsx) | Rating display | ✅ Existing |

## Design Tokens

### Color Palette

#### Primary Colors (HSL)
- **Background**: `hsl(var(--background))` - Page background
- **Foreground**: `hsl(var(--foreground))` - Primary text
- **Primary**: `hsl(var(--primary))` - Brand color
- **Secondary**: `hsl(var(--secondary))` - Secondary actions
- **Accent**: `hsl(var(--accent))` - Highlights
- **Destructive**: `hsl(var(--destructive))` - Error/delete actions

#### Semantic Colors
- **Success**: Green (#22c55e)
- **Warning**: Yellow (#eab308)
- **Info**: Blue (#3b82f6)
- **Error**: Red (#ef4444)

### Spacing Scale

Standard Tailwind spacing:
- `px-1` (0.25rem / 4px)
- `px-2` (0.5rem / 8px)
- `px-3` (0.75rem / 12px)
- `px-4` (1rem / 16px)
- `px-6` (1.5rem / 24px)
- `px-8` (2rem / 32px)

### Border Radius

- **sm**: `calc(var(--radius) - 4px)` - Small elements
- **md**: `calc(var(--radius) - 2px)` - Default inputs
- **lg**: `var(--radius)` - Cards, dialogs
- **full**: Pills and badges

### Typography

- **text-xs**: 0.75rem - Small labels, badges
- **text-sm**: 0.875rem - Body text, inputs
- **text-base**: 1rem - Default
- **text-lg**: 1.125rem - Dialog titles
- **text-xl**: 1.25rem - Section headers
- **text-2xl**: 1.5rem - Card titles

## Usage Examples

### Button Variants

```tsx
import { Button } from '@/components/ui/button';

// Default button
<Button>Click me</Button>

// Variants
<Button variant="destructive">Delete</Button>
<Button variant="outline">Cancel</Button>
<Button variant="secondary">Secondary</Button>
<Button variant="ghost">Ghost</Button>
<Button variant="link">Link</Button>

// Sizes
<Button size="sm">Small</Button>
<Button size="lg">Large</Button>
<Button size="icon">🔍</Button>
```

### Input with Label

```tsx
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

<Label htmlFor="email">Email</Label>
<Input id="email" type="email" placeholder="Enter your email" />
```

### Card Layout

```tsx
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

<Card>
  <CardHeader>
    <CardTitle>Card Title</CardTitle>
    <CardDescription>Card description</CardDescription>
  </CardHeader>
  <CardContent>
    <p>Main content goes here</p>
  </CardContent>
  <CardFooter>
    <Button>Action</Button>
  </CardFooter>
</Card>
```

### Badge Variants

```tsx
import { Badge } from '@/components/ui/badge';

<Badge>Default</Badge>
<Badge variant="success">Completed</Badge>
<Badge variant="warning">Pending</Badge>
<Badge variant="info">New</Badge>
<Badge variant="destructive">Cancelled</Badge>
```

### Alert Messages

```tsx
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';

<Alert variant="success">
  <AlertTitle>Success!</AlertTitle>
  <AlertDescription>Your action was completed.</AlertDescription>
</Alert>

<Alert variant="destructive">
  <AlertTitle>Error!</AlertTitle>
  <AlertDescription>Something went wrong.</AlertDescription>
</Alert>
```

### Dialog/Modal

```tsx
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';

<Dialog>
  <DialogTrigger asChild>
    <Button>Open Dialog</Button>
  </DialogTrigger>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Dialog Title</DialogTitle>
    </DialogHeader>
    <p>Dialog content</p>
    <DialogFooter>
      <Button>Save</Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

## Best Practices

1. **Always use UI components** - Don't create custom styled elements when a UI component exists
2. **Use variants** - Leverage CVA variants instead of custom className overrides
3. **Maintain consistency** - Use the same spacing and sizing across components
4. **Accessibility first** - All components include proper ARIA attributes
5. **Dark mode support** - Components automatically adapt to dark mode

## Adding New Components

When creating new UI components:

1. Use `React.forwardRef` for ref support
2. Export type definitions
3. Use `cn()` utility for className merging
4. Follow CVA pattern for variants
5. Include proper TypeScript interfaces
6. Add to this README

## Theme Configuration

The theme is defined in `app/globals.css` using CSS custom properties. To customize:

```css
@layer base {
  :root {
    --primary: 222.2 47.4% 11.2%;
    --primary-foreground: 210 40% 98%;
    /* ... other tokens */
  }
}
```

## Migration Guide

If updating old components:

1. Replace custom button styles with `<Button>` component
2. Use `<Card>` instead of manual div containers
3. Replace `<input>` with `<Input>` for consistent styling
4. Use `<Badge>` for status indicators
5. Use `<Alert>` for notifications

## Resources

- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
- [CVA Documentation](https://cva.style/docs)
- [Radix UI Documentation](https://www.radix-ui.com/)
- [Lucide Icons](https://lucide.dev/)
