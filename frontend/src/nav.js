import {
  BadgePercent,
  ChartColumn,
  CreditCard,
  FileText,
  Layers,
  LayoutDashboard,
  Package,
  PlayCircle,
  Receipt,
  Repeat,
  Percent,
  Store,
  UserRound,
  Users,
} from 'lucide-react'

const dashboard = { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard }

export const NAV_GROUPS = {
  admin: [
    { label: 'Overview', items: [dashboard, { to: '/reports', label: 'Reports', icon: ChartColumn }] },
    {
      label: 'Sales',
      items: [
        { to: '/quotations', label: 'Quotations', icon: FileText },
        { to: '/subscriptions', label: 'Subscriptions', icon: Repeat },
      ],
    },
    {
      label: 'Billing',
      items: [
        { to: '/invoices', label: 'Invoices', icon: Receipt },
        { to: '/payments', label: 'Payments', icon: CreditCard },
        { to: '/billing-run', label: 'Billing run', icon: PlayCircle },
      ],
    },
    {
      label: 'Catalog',
      items: [
        { to: '/products', label: 'Products', icon: Package },
        { to: '/plans', label: 'Plans', icon: Layers },
        { to: '/tax-rules', label: 'Tax rules', icon: Percent },
        { to: '/discounts', label: 'Discounts', icon: BadgePercent },
      ],
    },
    { label: 'People', items: [{ to: '/users', label: 'Users', icon: Users }] },
  ],
  staff: [
    { label: 'Overview', items: [dashboard, { to: '/reports', label: 'Reports', icon: ChartColumn }] },
    {
      label: 'Sales',
      items: [
        { to: '/users', label: 'Customers', icon: Users },
        { to: '/quotations', label: 'Quotations', icon: FileText },
        { to: '/subscriptions', label: 'Subscriptions', icon: Repeat },
      ],
    },
    {
      label: 'Billing',
      items: [
        { to: '/invoices', label: 'Invoices', icon: Receipt },
        { to: '/payments', label: 'Payments', icon: CreditCard },
        { to: '/billing-run', label: 'Billing run', icon: PlayCircle },
      ],
    },
    {
      label: 'Reference',
      items: [
        { to: '/tax-rules', label: 'Tax rules', icon: Percent },
        { to: '/discounts', label: 'Discounts', icon: BadgePercent },
      ],
    },
  ],
  customer: [
    { label: 'Portal', items: [dashboard, { to: '/browse-plans', label: 'Browse plans', icon: Store }] },
    {
      label: 'My account',
      items: [
        { to: '/subscriptions', label: 'My subscriptions', icon: Repeat },
        { to: '/quotations', label: 'My quotations', icon: FileText },
        { to: '/invoices', label: 'Invoices', icon: Receipt },
        { to: '/payments', label: 'Payment history', icon: CreditCard },
        { to: '/account', label: 'Profile & security', icon: UserRound },
      ],
    },
  ],
}

export const flatNav = (role) => (NAV_GROUPS[role] ?? NAV_GROUPS.customer).flatMap((group) => group.items)
