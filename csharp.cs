// This C# script is designed for a Unity project to receive telemetry data from a ROS 2 node via TCP and update the UI elements of a P1-style dashboard in real-time. The script uses multi-threading to handle incoming data without blocking the main Unity thread, ensuring smooth performance. It includes error handling for network issues and allows for easy customization of UI elements through the Unity Inspector.

using System;
using System.IO;
using System.Net.Sockets;
using System.Threading;
using UnityEngine;
using TMPro;

public class TelemetryDispatcher : MonoBehaviour
{
    [Header("Network Pipeline Settings")]
    public string ipAddress = "127.0.0.1";
    public int port = 10005;

    [Header("P1 UI Scene References")]
    public Transform speedNeedleTransform;    // Assign your Red Dial Needle here
    [cite_start]public TextMeshProUGUI digitalSpeedText;   // Assign the Digital Speed Text component [cite: 4]
    public Transform altitudeTapeTrack;       // Assign the 'Tape_Numbers' moving vertical layer
    public TextMeshProUGUI digitalAltText;     // Assign a digital Altitude text readout if you have one [cite: 43]

    // Multi-threaded Data Variables
    private TcpClient client;
    private Thread receiveThread;
    private bool isRunning = false;

    // Parsed outputs shared between threads
    private float sharedSpeed = 0f;
    private float sharedAltitude = 0f;
    private readonly object lockObject = new object();

    void Start()
    {
        isRunning = true;
        // Run network ingestion on a secondary thread to protect frame performance
        receiveThread = new Thread(ReceiveData);
        receiveThread.IsBackground = true;
        receiveThread.Start();
    }

    void Update()
    {
        float currentSpeed;
        float currentAltitude;

        // Thread-safe data extraction
        lock (lockObject)
        {
            currentSpeed = sharedSpeed;
            currentAltitude = sharedAltitude;
        }

        // Animate Your Dashboard Elements!
        AnimateDashboard(currentSpeed, currentAltitude);
    }

    private void ReceiveData()
    {
        while (isRunning)
        {
            try
            {
                if (client == null || !client.Connected)
                {
                    client = new TcpClient(ipAddress, port);
                }

                using (NetworkStream stream = client.GetStream())
                using (StreamReader reader = new StreamReader(stream))
                {
                    while (isRunning && client.Connected)
                    {
                        string rawData = reader.ReadLine(); // Deserializer parses line segments split by '\n'
                        if (!string.IsNullOrEmpty(rawData))
                        {
                            ParseAndProcess(rawData);
                        }
                    }
                }
            }
            catch (Exception)
            {
                // Simple socket retry loop logic to prevent crash states
                Thread.Sleep(1000);
            }
        }
    }

    private void ParseAndProcess(string data)
    {
        try
        {
            // Expected data packet string: "SPEED,ALTITUDE"
            string[] pieces = data.Split(',');
            if (pieces.Length >= 2)
            {
                float parsedSpeed = float.Parse(pieces[0]);
                float parsedAlt = float.Parse(pieces[1]);

                lock (lockObject)
                {
                    sharedSpeed = parsedSpeed;
                    sharedAltitude = parsedAlt;
                }
            }
        }
        catch (Exception ex)
        {
            Debug.LogWarning("Deserialization Parsing Error: " + ex.Message);
        }
    }

    private void AnimateDashboard(float speed, float altitude)
    {
        // 1. Car-Style Speed Needle Rotation Animation
        if (speedNeedleTransform != null)
        {
            // Maps 0-60 KPH onto a circular layout sweeping from -120 to +120 degrees
            float targetRotationAngle = (speed * 4.0f) - 120.0f;
            speedNeedleTransform.localRotation = Quaternion.Euler(0f, 0f, -targetRotationAngle);
        }

        // 2. Digital Speed Text Update
        if (digitalSpeedText != null)
        {
            digitalSpeedText.text = speed.ToString("F0") + " KPH";
        }

        // 3. Vertical Moving Altitude Tape Animation
        if (altitudeTapeTrack != null)
        {
            // Adjust the multiplier value (e.g., 5.0f) to match your custom font tick sizing spacing inside Unity
            float verticalOffsetPosition = (altitude / 20f - 300f) * 5.0f;
            altitudeTapeTrack.localPosition = new Vector3(altitudeTapeTrack.localPosition.x, verticalOffsetPosition, altitudeTapeTransform.localPosition.z);
        }
    }

    void OnDestroy()
    {
        isRunning = false;
        if (client != null) client.Close();
        if (receiveThread != null) receiveThread.Abort();
    }
}