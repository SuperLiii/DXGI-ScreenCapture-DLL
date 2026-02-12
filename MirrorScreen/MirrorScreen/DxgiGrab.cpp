#include "DxgiGrab.h"
#include <d3d11.h>
#include <dxgi1_2.h>

#pragma comment(lib, "D3D11.lib")
#pragma comment(lib, "DXGI.lib")

#define RESET_OBJECT(obj)                                                                                              \
    do {                                                                                                               \
        if (obj) obj->Release();                                                                                       \
        obj = nullptr;                                                                                                 \
    } while (0)

struct DxgiInfo {
    DxgiInfo() {}
    ~DxgiInfo() {
        RESET_OBJECT(m_pDevice);
        RESET_OBJECT(m_pContext);
        RESET_OBJECT(m_pDeskDupl);
    }

    ID3D11Device *m_pDevice = nullptr;
    ID3D11DeviceContext *m_pContext = nullptr;
    IDXGIOutputDuplication *m_pDeskDupl = nullptr;
    int m_nWidth = 0;
    int m_nHeight = 0;
};

void *dxgi_create(void) {
    DxgiInfo *pDxgiInfo = new DxgiInfo;

    // Driver types supported
    D3D_DRIVER_TYPE DriverTypes[] = {
        D3D_DRIVER_TYPE_HARDWARE,
        D3D_DRIVER_TYPE_WARP,
        D3D_DRIVER_TYPE_REFERENCE,
    };
    UINT uNumDriverTypes = ARRAYSIZE(DriverTypes);

    // Feature levels supported
    D3D_FEATURE_LEVEL FeatureLevels[] = {
        D3D_FEATURE_LEVEL_11_0,
        D3D_FEATURE_LEVEL_10_1,
        D3D_FEATURE_LEVEL_10_0,
        D3D_FEATURE_LEVEL_9_1,
    };
    UINT uNumFeatureLevels = ARRAYSIZE(FeatureLevels);

    //
    // Create D3D device
    //
    HRESULT hResult = -1;
    for (UINT DriverTypeIndex = 0; DriverTypeIndex < uNumDriverTypes; ++DriverTypeIndex) {
        D3D_FEATURE_LEVEL FeatureLevel;
        hResult = D3D11CreateDevice(
            nullptr,
            DriverTypes[DriverTypeIndex],
            nullptr,
            0,
            FeatureLevels,
            uNumFeatureLevels,
            D3D11_SDK_VERSION,
            &pDxgiInfo->m_pDevice,
            &FeatureLevel,
            &pDxgiInfo->m_pContext);
        if (SUCCEEDED(hResult)) {
            break;
        }
    }
    if (FAILED(hResult)) {
        delete pDxgiInfo;
        return nullptr;
    }

    //
    // Get DXGI device
    //
    IDXGIDevice *pDxgiDevice = nullptr;
    hResult = pDxgiInfo->m_pDevice->QueryInterface(__uuidof(IDXGIDevice), reinterpret_cast<void **>(&pDxgiDevice));
    if (FAILED(hResult)) {
        delete pDxgiInfo;
        return nullptr;
    }

    //
    // Get DXGI adapter
    //
    IDXGIAdapter *pDxgiAdapter = nullptr;
    hResult = pDxgiDevice->GetParent(__uuidof(IDXGIAdapter), reinterpret_cast<void **>(&pDxgiAdapter));
    RESET_OBJECT(pDxgiDevice);
    if (FAILED(hResult)) {
        delete pDxgiInfo;
        return nullptr;
    }

    //
    // Get output
    //
    INT nOutput = 0;
    IDXGIOutput *pDxgiOutput = nullptr;
    hResult = pDxgiAdapter->EnumOutputs(nOutput, &pDxgiOutput);
    RESET_OBJECT(pDxgiAdapter);
    if (FAILED(hResult)) {
        delete pDxgiInfo;
        return nullptr;
    }

    //
    // get output description struct
    //
    DXGI_OUTPUT_DESC dxgiOutDesc;
    pDxgiOutput->GetDesc(&dxgiOutDesc);
    pDxgiInfo->m_nWidth = dxgiOutDesc.DesktopCoordinates.right - dxgiOutDesc.DesktopCoordinates.left;
    pDxgiInfo->m_nHeight = dxgiOutDesc.DesktopCoordinates.bottom - dxgiOutDesc.DesktopCoordinates.top;

    //
    // QI for Output 1
    //
    IDXGIOutput1 *pDxgiOutput1 = nullptr;
    hResult = pDxgiOutput->QueryInterface(__uuidof(pDxgiOutput1), reinterpret_cast<void **>(&pDxgiOutput1));
    RESET_OBJECT(pDxgiOutput);
    if (FAILED(hResult)) {
        delete pDxgiInfo;
        return nullptr;
    }

    //
    // Create desktop duplication
    //
    hResult = pDxgiOutput1->DuplicateOutput(pDxgiInfo->m_pDevice, &pDxgiInfo->m_pDeskDupl);
    RESET_OBJECT(pDxgiOutput1);
    if (FAILED(hResult)) {
        delete pDxgiInfo;
        return nullptr;
    }

    return pDxgiInfo;
}

void dxgi_destroy(void *pDxgi) {
    DxgiInfo *pDxgiInfo = reinterpret_cast<DxgiInfo *>(pDxgi);
    delete pDxgiInfo;
}

int dxgi_get_size(void *pDxgi) {
    DxgiInfo *pDxgiInfo = reinterpret_cast<DxgiInfo *>(pDxgi);
    return pDxgiInfo->m_nWidth * pDxgiInfo->m_nHeight * 4;
}

int dxgi_get_width(void *pDxgi) {
    DxgiInfo *pDxgiInfo = reinterpret_cast<DxgiInfo *>(pDxgi);
    return pDxgiInfo->m_nWidth;
}

int dxgi_get_height(void *pDxgi) {
    DxgiInfo *pDxgiInfo = reinterpret_cast<DxgiInfo *>(pDxgi);
    return pDxgiInfo->m_nHeight;
}

FrameStatus dxgi_get_frame(void *pDxgi, char *pOut, int timeoutInMs) {
    DxgiInfo *pDxgiInfo = reinterpret_cast<DxgiInfo *>(pDxgi);
    IDXGIResource *pDesktopResource = nullptr;
    DXGI_OUTDUPL_FRAME_INFO FrameInfo;

    HRESULT hResult = pDxgiInfo->m_pDeskDupl->AcquireNextFrame(timeoutInMs, &FrameInfo, &pDesktopResource);
    if (FAILED(hResult)) {
        return hResult == DXGI_ERROR_WAIT_TIMEOUT ? FS_TIMEOUT : FS_ERROR;
    }

    //
    // query next frame staging buffer
    //
    ID3D11Texture2D *pAcquiredDesktopImage = nullptr;
    hResult =
        pDesktopResource->QueryInterface(__uuidof(ID3D11Texture2D), reinterpret_cast<void **>(&pAcquiredDesktopImage));
    RESET_OBJECT(pDesktopResource);
    if (FAILED(hResult)) {
        return FS_ERROR;
    }

    //
    // copy old description
    //
    D3D11_TEXTURE2D_DESC frameDescriptor;
    pAcquiredDesktopImage->GetDesc(&frameDescriptor);

    //
    // create a new staging buffer for fill frame image
    //
    ID3D11Texture2D *hNewDesktopImage = nullptr;
    frameDescriptor.Usage = D3D11_USAGE_STAGING;
    frameDescriptor.CPUAccessFlags = D3D11_CPU_ACCESS_READ;
    frameDescriptor.Format = DXGI_FORMAT_B8G8R8A8_UNORM;
    frameDescriptor.BindFlags = 0;
    frameDescriptor.MiscFlags = 0;
    frameDescriptor.MipLevels = 1;
    frameDescriptor.ArraySize = 1;
    frameDescriptor.SampleDesc.Count = 1;
    hResult = pDxgiInfo->m_pDevice->CreateTexture2D(&frameDescriptor, nullptr, &hNewDesktopImage);
    if (FAILED(hResult)) {
        return FS_ERROR;
    }

    //
    // copy next staging buffer to new staging buffer
    //
    pDxgiInfo->m_pContext->CopyResource(hNewDesktopImage, pAcquiredDesktopImage);

    D3D11_MAPPED_SUBRESOURCE dsec = {0};
    hResult = pDxgiInfo->m_pContext->Map(hNewDesktopImage, 0, D3D11_MAP_READ, 0, &dsec);
    if (SUCCEEDED(hResult)) {
        if (dsec.pData != nullptr) {
            for (int y = 0; y < pDxgiInfo->m_nHeight; ++y) {
                memcpy(
                    pOut + y * pDxgiInfo->m_nWidth * 4,
                    (char *)dsec.pData + y * dsec.RowPitch,
                    pDxgiInfo->m_nWidth * 4);
            }
        }
        pDxgiInfo->m_pContext->Unmap(hNewDesktopImage, 0);
    }

    RESET_OBJECT(pAcquiredDesktopImage);
    RESET_OBJECT(hNewDesktopImage);

    pDxgiInfo->m_pDeskDupl->ReleaseFrame();
    return dsec.pData != nullptr ? FS_OK : FS_ERROR;
}
