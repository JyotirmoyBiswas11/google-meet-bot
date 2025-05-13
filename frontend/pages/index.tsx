'use client';

import React, { useEffect, useState, ChangeEvent } from 'react';
import { meet, MeetSidePanelClient } from '@googleworkspace/meet-addons';
import axios from 'axios';
import AuthorizeButton from './components/AuthorizeButton';


export default function Page() {
    const [sidePanelClient, setSidePanelClient] = useState<MeetSidePanelClient | null>(null);

    useEffect(() => {
        (async () => {
            try {
                const session = await meet.addon.createAddonSession({
                    cloudProjectNumber: '104993485724',
                });
                const client = await session.createSidePanelClient();
                setSidePanelClient(client);
            } catch (error) {
                console.error('Error initializing Meet Side Panel Client:', error);
            }
        })();
    }, []);
    return (
        <div className="App justify-between">
            <header className="App-header">
                <h1>Google Meet Authorization</h1>
                <AuthorizeButton />
            </header>
        </div>
    );
}