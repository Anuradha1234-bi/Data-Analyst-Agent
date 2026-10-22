import React from 'react';
import { Outlet } from 'react-router-dom';
import { Navbar } from '../components/Navbar';
import { ErrorBoundary } from '../components/ErrorBoundary';

export const MainLayout = () => {
  return (
    <div className="min-h-screen flex flex-col bg-[#F4F6F9] dark:bg-[#070D1E] text-[#0F172A] dark:text-[#F8FAFC] font-sans selection:bg-[#2563EB] selection:text-white">
      {/* Professional Enterprise-Grade Dark Navy & Blue Navbar */}
      <Navbar />

      {/* Main Application Content Area */}
      <main className="flex-1 w-full overflow-y-auto p-4 sm:p-6 lg:p-7 bg-[#F4F6F9] dark:bg-[#070D1E]">
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
      </main>
    </div>
  );
};

export default MainLayout;
