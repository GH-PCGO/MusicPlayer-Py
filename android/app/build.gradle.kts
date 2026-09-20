plugins {
    id("com.android.application")
    id("com.chaquo.python")
}

android {
    namespace = "com.musicplayer.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.musicplayer.app"
        minSdk = 29          // MediaStore RELATIVE_PATH/IS_PENDING 需要 API 29+
        targetSdk = 34
        versionCode = 11
        versionName = "2.0"
        ndk {
            // 瑕嗙洊缁濆ぇ澶氭暟鐪熸満; 濡傞渶 32 浣嶈€佽澶囧彲鏀圭敤 Python 3.11 + armeabi-v7a
            abiFilters += listOf("arm64-v8a", "armeabi-v7a")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

chaquopy {
    defaultConfig {
        version = "3.11"
        // 构建机 Python 3.11: 优先本机 Windows 工具链, 回退作者 mac 路径, 再回退 PATH
        val winPy = "D:/WorkSpace/Personal-PC/Music/AndroidToolchain/python311/python.exe"
        val macPy = "/Users/conquer/android-toolchain/python311/bin/python3"
        buildPython(
            when {
                file(winPy).exists() -> winPy
                file(macPy).exists() -> macPy
                else -> "python"
            }
        )
        pip {
            // 绾?Python 渚濊禆; 璧?TUNA 闀滃儚鍔犻€?            options("--index-url", "https://pypi.tuna.tsinghua.edu.cn/simple")
            install("requests")
            install("certifi")
        }
    }
    sourceSets {
        getByName("main") {
            // 澶嶇敤妗岄潰鐗堢函閫昏緫 (kuwo / lyrics / paths / util)
            srcDir("../../src")
        }
    }
}








