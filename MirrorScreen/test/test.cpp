// test.cpp : This file contains the 'main' function. Program execution begins and ends there.
//
#include <Windows.h>
#include <iostream>
#include "../MirrorScreen/DxgiGrab.h"

int main()
{
    void* dxgi = dxgi_create();
    int numAlloc = dxgi_get_size(dxgi);
    char* data = (char*)malloc(numAlloc);
    for (int i = 0; i < 100000; ++i)
    {
        FrameStatus status = dxgi_get_frame(dxgi, data, 10);
        switch (status)
        {
        case FS_OK:
            printf("ok[%d]\n", i);
            break;
        case FS_TIMEOUT:
            break;
        case FS_ERROR:
            printf("error\n");
            return 1;
        }
    }
    dxgi_destroy(dxgi);
}

// Run program: Ctrl + F5 or Debug > Start Without Debugging menu
// Debug program: F5 or Debug > Start Debugging menu

// Tips for Getting Started: 
//   1. Use the Solution Explorer window to add/manage files
//   2. Use the Team Explorer window to connect to source control
//   3. Use the Output window to see build output and other messages
//   4. Use the Error List window to view errors
//   5. Go to Project > Add New Item to create new code files, or Project > Add Existing Item to add existing code files to the project
//   6. In the future, to open this project again, go to File > Open > Project and select the .sln file
