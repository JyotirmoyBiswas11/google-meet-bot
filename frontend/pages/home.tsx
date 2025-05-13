'use client';

import React, { useEffect, useState, ChangeEvent } from 'react';
import { meet, MeetSidePanelClient } from '@googleworkspace/meet-addons';
import axios from 'axios';



export default function Page() {
    const [sidePanelClient, setSidePanelClient] = useState<MeetSidePanelClient | null>(null);
    const [meetData,setMeetData] = useState({})

    useEffect(() => {
        (async () => {
            try {
                const session = await meet.addon.createAddonSession({
                    cloudProjectNumber: '104993485724',
                });
                const client = await session.createSidePanelClient();
                setSidePanelClient(client);
                const meetDetails= await client.getMeetingInfo()
                setMeetData(meetDetails)
                console.log("meet details",meetData);
                
            } catch (error) {
                console.error('Error initializing Meet Side Panel Client:', error);
            }
        })();
    }, []);


    const [meetingId, setMeetingId] = useState<string>('');
    const [summary, setSummary] = useState<string | { error?: string, [key: string]: any }>('Enter a meeting ID to generate summary.');
    const [isLoading, setIsLoading] = useState<boolean>(false);

    const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
        setMeetingId(e.target.value);
    };

    const handleGenerateSummary = () => {
        if (!validateMeetingId(meetingId)) {
            setSummary('Invalid meeting ID. Please enter a valid meeting ID.');
            return;
        }

        setIsLoading(true);
        axios.get(`http://127.0.0.1:5000/summary/${meetingId}`)
            .then(response => {
                setSummary('Waiting for transcript generation...');
                pollSummaryStatus();
            })
            .catch(error => {
                console.error('Error initiating summary generation:', error);
                setSummary({ error: 'Error initiating summary generation.' });
                setIsLoading(false);
            });
    };

    const validateMeetingId = (meetingId: string) => {
        const regex = /^([a-z0-9]{10}|([a-z0-9]{1,4}-){0,2}[a-z0-0]{1,4})$/;
        return regex.test(meetingId);
    };

    const pollSummaryStatus = () => {
        const intervalId = setInterval(() => {
            axios.get('http://127.0.0.1:5000/summary_status')
                .then(response => {
                    if (response.data.message === 'insufficient_quota') {
                        setSummary({ error: 'You have exceeded your quota. Please check your plan and billing details.' });
                        clearInterval(intervalId);
                        setIsLoading(false);
                    } else if (response.data.message !== 'loading') {
                        setSummary(response.data);
                        clearInterval(intervalId);
                        setIsLoading(false);
                    } else {
                        setSummary('Loading summary...');
                    }
                })
                .catch(error => {
                    console.error('Error polling summary status:', error);
                    clearInterval(intervalId);
                    setSummary({ error: 'Error polling summary status.' });
                    setIsLoading(false);
                });
        }, 5000);
    };

    return (
        <div className="App h-screen flex flex-col items-center justify-center bg-gray-100">
            <header className="bg-white p-6 rounded shadow-md w-full max-w-md">
                <h1 className="text-2xl font-bold mb-4 text-center text-black">Meeting Summary Generator</h1>
                <input
                    className="border p-2 w-full mb-4 rounded text-black"
                    type="text"
                    placeholder="Enter Meeting ID"
                    value={meetingId}
                    onChange={handleInputChange}
                />
                <button
                    className="bg-blue-500 text-white p-2 w-full rounded"
                    onClick={handleGenerateSummary}
                >
                    Generate Summary
                </button>
                <div className="summary-container mt-6 text-black">
                    {isLoading ? <LoadingDots /> : renderSummary(summary)}
                </div>
            </header>
        </div>
    );
}

const LoadingDots = () => (
    <div className="loading-dots">
        <p className='text-black'>Waiting for transcript generation</p>
        <span>.</span>
        <span>.</span>
        <span>.</span>
        <style jsx>{`
            .loading-dots {
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 24px;
            }
            .loading-dots span {
                margin: 0 2px;
                animation: blink 1s infinite alternate;
            }
            .loading-dots span:nth-child(2) {
                animation-delay: 0.2s;
            }
            .loading-dots span:nth-child(3) {
                animation-delay: 0.4s;
            }
            @keyframes blink {
                0% { opacity: 0; }
                100% { opacity: 1; }
            }
        `}</style>
    </div>
);

const renderSummary = (summary: string | { error?: string, [key: string]: any }) => {
    if (typeof summary === 'string') return <p className='text-black'>{summary}</p>;

    if (summary.error) {
        return <p className="text-red-500">{summary.error}</p>;
    }

    return (
        <div>
            <h2 className="text-xl font-semibold mb-2 text-black">Agenda</h2>
            <ul className="list-disc pl-5 text-black">
                {summary.agenda?.map((point: string, index: number) => (
                    <li key={index}>{point}</li>
                ))}
            </ul>

            <h2 className="text-xl font-semibold mt-4 mb-2 text-black">Key Decisions</h2>
            {Object.keys(summary.key_decisions || {}).map((key, index) => (
                <div key={index}>
                    <h3 className="font-semibold text-black">{key.charAt(0).toUpperCase() + key.slice(1)}</h3>
                    <ul className="list-disc pl-5 text-black">
                        {summary.key_decisions[key].map((decision: string, idx: number) => (
                            <li key={idx}>{decision}</li>
                        ))}
                    </ul>
                </div>
            ))}

            <h2 className="text-xl font-semibold mt-4 mb-2 text-black">Action Items</h2>
            {summary.action_items?.map((item: any, index: number) => (
                <div key={index} className="mb-2 text-black">
                    <p><strong>Owner:</strong> {item.owner}</p>
                    <p><strong>Task:</strong> {item.task}</p>
                    <p><strong>Dependencies:</strong> {item.dependencies}</p>
                </div>
            ))}

            <h2 className="text-xl font-semibold mt-4 mb-2 text-black">Major Discussion Points</h2>
            {summary.major_discussion_points?.map((point: any, index: number) => (
                <div key={index} className="mb-2 text-black">
                    <p><strong>Topic:</strong> {point.topic}</p>
                    <p><strong>Context:</strong> {point.context}</p>
                    <p><strong>Resolution:</strong> {point.resolution}</p>
                </div>
            ))}

            <h2 className="text-xl font-semibold mt-4 mb-2 text-black">Next Steps</h2>
            {summary.next_steps?.map((step: any, index: number) => (
                <div key={index} className="mb-2 text-black">
                    <p><strong>Priority:</strong> {step.priority}</p>
                    <p><strong>Timeline:</strong> {step.timeline}</p>
                    <p><strong>Dependencies:</strong> {step.dependencies}</p>
                </div>
            ))}

            <h2 className="text-xl font-semibold mt-4 mb-2 text-black">Additional Notes</h2>
            <ul className="list-disc pl-5 text-black">
                {summary.additional_notes?.map((note: string, index: number) => (
                    <li key={index}>{note}</li>
                ))}
            </ul>
        </div>
    );
};
