import React from 'react';

const AuthorizeButton = () => {
    const handleAuthorize = () => {
        window.location.href = 'http://localhost:5000/authorize';
    };

    return (
        <div className="flex items-center justify-center min-h-screen bg-gray-100">
            <button onClick={handleAuthorize} className="bg-blue-500 text-white p-4 rounded-lg shadow-lg hover:bg-blue-600 transition duration-300 ease-in-out transform hover:scale-105">
                Authorize with Google
            </button>
        </div>
    );
};

export default AuthorizeButton;
