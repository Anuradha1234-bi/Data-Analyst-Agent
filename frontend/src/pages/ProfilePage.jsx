import React from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { User, Mail, Calendar, Shield, LogOut, CheckCircle } from 'lucide-react';

export const ProfilePage = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const displayName = user?.full_name || user?.name || 'Analyst';

  const formattedDate = user?.created_at
    ? new Date(user.created_at).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : 'Active Session';

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-bold text-[#0F172A]">User Account Profile</h1>
        <p className="text-xs text-[#64748B] mt-1">
          Personal account information and authentication credentials
        </p>
      </div>

      <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-xs space-y-6">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-[#2563EB] text-white flex items-center justify-center font-bold text-xl uppercase shadow-sm">
            {displayName ? displayName.charAt(0) : 'U'}
          </div>
          <div>
            <h2 className="text-base font-bold text-[#0F172A]">{displayName}</h2>
            <p className="text-xs text-[#64748B]">{user?.email}</p>
          </div>
        </div>

        <div className="divide-y divide-[#E2E8F0] text-xs">
          <div className="py-3 flex items-center justify-between">
            <span className="text-[#64748B] flex items-center gap-2">
              <User className="w-4 h-4 text-[#94A3B8]" />
              <span>Full Name</span>
            </span>
            <span className="font-semibold text-[#0F172A]">{displayName}</span>
          </div>

          <div className="py-3 flex items-center justify-between">
            <span className="text-[#64748B] flex items-center gap-2">
              <Mail className="w-4 h-4 text-[#94A3B8]" />
              <span>Email Address</span>
            </span>
            <span className="font-semibold text-[#0F172A]">{user?.email}</span>
          </div>

          <div className="py-3 flex items-center justify-between">
            <span className="text-[#64748B] flex items-center gap-2">
              <Calendar className="w-4 h-4 text-[#94A3B8]" />
              <span>Member Since</span>
            </span>
            <span className="font-semibold text-[#0F172A]">{formattedDate}</span>
          </div>

          <div className="py-3 flex items-center justify-between">
            <span className="text-[#64748B] flex items-center gap-2">
              <Shield className="w-4 h-4 text-[#94A3B8]" />
              <span>Account Status</span>
            </span>
            <span className="font-semibold text-[#16A34A] px-2.5 py-0.5 rounded-full bg-emerald-50 border border-emerald-200 inline-flex items-center gap-1.5">
              <CheckCircle className="w-3 h-3 text-[#16A34A]" />
              <span>Active</span>
            </span>
          </div>
        </div>

        <div className="pt-2 flex justify-end">
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 px-4 py-2 bg-red-50 hover:bg-red-100 border border-red-200 text-red-700 text-xs font-semibold rounded-lg transition-colors cursor-pointer"
          >
            <LogOut className="w-4 h-4" />
            <span>Sign Out</span>
          </button>
        </div>
      </div>
    </div>
  );
};
