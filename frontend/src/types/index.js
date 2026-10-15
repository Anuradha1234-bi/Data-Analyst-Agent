/**
 * Navigation item constants and type definitions.
 */

export const NavigationItems = [
  { id: 'dashboard', label: 'Dashboard', icon: 'LayoutDashboard', public: false },
  { id: 'datasets', label: 'Datasets', icon: 'Database', public: false },
  { id: 'profiling', label: 'Profiling', icon: 'Activity', public: false },
  { id: 'cleaning', label: 'Cleaning', icon: 'Sparkles', public: false },
  { id: 'anomalies', label: 'Anomalies', icon: 'AlertTriangle', public: false },
  { id: 'prediction', label: 'Prediction', icon: 'TrendingUp', public: false },
  { id: 'ask-analyst', label: 'Ask Analyst', icon: 'MessageSquareText', public: false },
  { id: 'reports', label: 'Reports', icon: 'FileText', public: false },
  { id: 'admin-users', label: 'Admin Users', icon: 'Shield', public: false, adminOnly: true },
];
